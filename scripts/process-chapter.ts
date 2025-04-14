const path = require('path');
const fs = require('fs');
const { exec } = require('child_process');
const { promisify } = require('util');
const { ROUTES } = require('../lib/routes-config');

interface EachRoute {
  title: string;
  href: string;
  noLink?: boolean;
  items?: EachRoute[];
}

const execAsync = promisify(exec);

interface ProcessChapterOptions {
  texFile: string;
  title: string;
}

async function updateRoutesConfig(title: string, href: string) {
  // Find or create the Chapters route
  let chaptersRoute = ROUTES.find((route: EachRoute) => route.title === "Chapters");
  if (!chaptersRoute) {
    chaptersRoute = {
      title: "Chapters",
      href: "/",
      noLink: true,
      items: []
    };
    ROUTES.push(chaptersRoute);
  }
  // Initialize items array if it doesn't exist
  if (!chaptersRoute.items) {
    chaptersRoute.items = [];
  }
  // Add new chapter if it doesn't exist
  const chapterExists = chaptersRoute.items.some((item: EachRoute) => item.href === href);
  if (!chapterExists) {
    chaptersRoute.items.push({
      title,
      href,
    });
    // Sort chapters alphabetically by title
    chaptersRoute.items.sort((a: EachRoute, b: EachRoute) => {
      // Keep Introduction always first
      if (a.title === "Introduction") return -1;
      if (b.title === "Introduction") return 1;
      return a.title.localeCompare(b.title);
    });
    // Generate the updated routes file content
    const routesContent = `export type EachRoute = {
      title: string;
      href: string;
      noLink?: true;
      items?: EachRoute[];
    };
    export const ROUTES: EachRoute[] = ${JSON.stringify(ROUTES, null, 2)};
    type Page = { title: string; href: string };
    function getRecurrsiveAllLinks(node: EachRoute) {
      const ans: Page[] = [];
      if (!node.noLink) {
        ans.push({ title: node.title, href: node.href });
      }
      node.items?.forEach((subNode) => {
        const temp = { ...subNode, href: \`\${node.href}\${subNode.href}\` };
        ans.push(...getRecurrsiveAllLinks(temp));
      });
      return ans;
    }
    export const page_routes = ROUTES.map((it) => getRecurrsiveAllLinks(it)).flat();
    `;
    // Write the updated routes back to the file
    fs.writeFileSync(
      path.join(process.cwd(), 'lib', 'routes-config.ts'),
      routesContent,
      'utf-8'
    );
  }
}

async function processChapter({ texFile, title }: ProcessChapterOptions) {
  try {
    // 1. Create the output directory path
    const chapterName = path.basename(texFile, '.tex');
    const outputDir = path.join(process.cwd(), 'contents', 'docs', 'chapters', chapterName);
    
    // 2. Convert .tex to .mdx using the Python script
    console.log(`Converting ${texFile} to MDX...`);
    await execAsync(`python3 scripts/convert_tex_to_md.py "${texFile}" "${outputDir}"`);
    
    // 3. Generate the href
    const href = `/${chapterName}`;
    
    // 4. Update routes configuration
    console.log('Updating routes...');
    await updateRoutesConfig(title, href);
    
    console.log(`
        Successfully processed chapter:
        - Converted ${texFile} to MDX
        - Placed in ${outputDir}/index.mdx
        - Updated routes with title: "${title}" and href: "${href}"
    `);
    
    return true;
  } catch (error) {
    console.error(`Error processing chapter ${texFile}:`, error);
    return false;
  }
}

/**
 * Processes all .tex files in the given directory
 */
async function processAllChapters(chaptersDir: string) {
  try {
    console.log(`Scanning directory: ${chaptersDir}`);
    
    // Check if directory exists
    if (!fs.existsSync(chaptersDir)) {
      console.error(`Directory not found: ${chaptersDir}`);
      process.exit(1);
    }
    
    // Read all files in the directory
    const files = fs.readdirSync(chaptersDir);
    
    // Filter for .tex files
    const texFiles = files.filter((file: string) => file.toLowerCase().endsWith('.tex'));
    
    if (texFiles.length === 0) {
      console.log(`No .tex files found in ${chaptersDir}`);
      return;
    }
    
    console.log(`Found ${texFiles.length} .tex files to process`);
    
    // Process each file
    let successCount = 0;
    let failCount = 0;
    
    for (const file of texFiles) {
      const texFile = path.join(chaptersDir, file);
      const title = path.basename(file, '.tex')
        .split('_')
        .map((word: string) => word.charAt(0).toUpperCase() + word.slice(1))
        .join(' ');
      
      console.log(`\nProcessing ${file} with title "${title}"...`);
      
      const success = await processChapter({ texFile, title });
      if (success) {
        successCount++;
      } else {
        failCount++;
      }
    }
    
    console.log(`\nProcessing complete!`);
    console.log(`Successfully processed: ${successCount} files`);
    if (failCount > 0) {
      console.log(`Failed to process: ${failCount} files`);
    }
    
  } catch (error) {
    console.error('Error processing chapters:', error);
    process.exit(1);
  }
}

// Main execution
if (require.main === module) {
  const args = process.argv.slice(2);
  
  if (args.length === 0) {
    // Default mode: process all chapters in the default directory
    const chaptersDir = path.join(process.cwd(), 'chapters');
    processAllChapters(chaptersDir);
  } else if (args.length === 1) {
    // Alternative mode: process all chapters in the specified directory
    const chaptersDir = args[0];
    processAllChapters(chaptersDir);
  } else if (args.length === 2) {
    // Legacy mode: process a single chapter
    const [texFile, title] = args;
    processChapter({ texFile, title });
  } else {
    console.error(`
Usage: 
  ts-node process-chapter.ts                      # Process all chapters in default 'chapters' directory
  ts-node process-chapter.ts <chapters-directory> # Process all chapters in specified directory
  ts-node process-chapter.ts <tex-file> <title>   # Process a single chapter
`);
    process.exit(1);
  }
}