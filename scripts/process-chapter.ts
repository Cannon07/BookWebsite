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
  forceUpdate?: boolean;  // New option to force update even if already processed
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

/**
 * Check if a chapter needs to be reprocessed by comparing file modification times
 */
function shouldProcessChapter(texFile: string, outputDir: string, forceUpdate: boolean = false): boolean {
  // Always process if forced
  if (forceUpdate) {
    return true;
  }
  
  // Process if output directory doesn't exist
  if (!fs.existsSync(outputDir)) {
    return true;
  }
  
  // Check if the main output file exists
  const outputFile = path.join(outputDir, 'index.mdx');
  if (!fs.existsSync(outputFile)) {
    return true;
  }
  
  try {
    // Get modification times
    const texStats = fs.statSync(texFile);
    const outputStats = fs.statSync(outputFile);
    
    // Process if tex file is newer than output file
    if (texStats.mtime > outputStats.mtime) {
      return true;
    }
    
    // Check if conversion script has been modified more recently than output
    const conversionScript = path.join(process.cwd(), 'scripts', 'convert_tex_to_md.py');
    if (fs.existsSync(conversionScript)) {
      const scriptStats = fs.statSync(conversionScript);
      if (scriptStats.mtime > outputStats.mtime) {
        return true;
      }
    }
    
    return false;
  } catch (error) {
    console.warn(`Warning: Could not check file times for ${texFile}, processing anyway:`, error);
    return true;
  }
}

async function processChapter({ texFile, title, forceUpdate = false }: ProcessChapterOptions) {
  try {
    // 1. Create the output directory path
    const chapterName = path.basename(texFile, '.tex');
    const outputDir = path.join(process.cwd(), 'contents', 'docs', 'chapters', chapterName);
    
    // 2. Smart check: should we process this chapter?
    const needsProcessing = shouldProcessChapter(texFile, outputDir, forceUpdate);
    
    if (!needsProcessing) {
      console.log(`Skipping ${texFile} - up to date (source not modified since last conversion)`);
      
      // Still update routes configuration if needed
      const href = `/${chapterName}`;
      await updateRoutesConfig(title, href);
      
      return { status: 'skipped', reason: 'up to date' };
    }
    
    // 3. Process the chapter (it's new or has been modified)
    const outputFile = path.join(outputDir, 'index.mdx');
    const isNewChapter = !fs.existsSync(outputFile);
    
    console.log(`${isNewChapter ? 'Converting new chapter' : 'Updating modified chapter'}: ${texFile}`);
    
    // 4. Convert .tex to .mdx using the Python script
    console.log(`Converting ${texFile} to MDX...`);
    await execAsync(`python3 scripts/convert_tex_to_md.py "${texFile}" "${outputDir}"`);
    
    // 5. Generate the href
    const href = `/${chapterName}`;
    
    // 6. Update routes configuration
    console.log('Updating routes...');
    await updateRoutesConfig(title, href);
    
    console.log(`
        Successfully processed chapter:
        - ${isNewChapter ? 'Converted new' : 'Updated existing'} ${texFile} to MDX
        - Placed in ${outputDir}/index.mdx
        - Updated routes with title: "${title}" and href: "${href}"
    `);
    
    return { status: 'success', wasNew: isNewChapter };
  } catch (error) {
    console.error(`Error processing chapter ${texFile}:`, error);
    return { status: 'error', error };
  }
}

/**
 * Processes .tex files in the given directory, checking modification times to determine what needs updating
 */
async function processAllChapters(chaptersDir: string, options = { onlyNewChapters: true }) {
  try {
    console.log(`Scanning directory: ${chaptersDir}`);
    console.log(`Processing mode: ${options.onlyNewChapters ? 'Smart update (only new/modified chapters)' : 'Force update all chapters'}`);
    
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
    
    console.log(`Found ${texFiles.length} .tex files to check`);
    
    // Process each file
    let newCount = 0;
    let updatedCount = 0;
    let skippedCount = 0;
    let errorCount = 0;
    
    for (const file of texFiles) {
      const texFile = path.join(chaptersDir, file);
      const title = path.basename(file, '.tex')
        .split('_')
        .map((word: string) => word.charAt(0).toUpperCase() + word.slice(1))
        .join(' ');
      
      console.log(`\nChecking ${file} with title "${title}"...`);
      
      const result = await processChapter({ 
        texFile, 
        title,
        forceUpdate: !options.onlyNewChapters  // Force update if not in onlyNewChapters mode
      });
      
      if (result.status === 'success') {
        if (result.wasNew) {
          newCount++;
        } else {
          updatedCount++;
        }
      } else if (result.status === 'skipped') {
        skippedCount++;
      } else {
        errorCount++;
      }
    }
    
    console.log(`\nProcessing complete!`);
    console.log(`New chapters processed: ${newCount}`);
    console.log(`Existing chapters updated: ${updatedCount}`);
    console.log(`Chapters skipped (up to date): ${skippedCount}`);
    if (errorCount > 0) {
      console.log(`Failed to process: ${errorCount} files`);
    }
    
    // Summary
    const totalProcessed = newCount + updatedCount;
    if (totalProcessed > 0) {
      console.log(`\n✅ Successfully processed ${totalProcessed} chapters total`);
    } else {
      console.log(`\n✅ All chapters are up to date`);
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
    // Default mode: process only new/modified chapters in the default directory
    const chaptersDir = path.join(process.cwd(), 'chapters');
    processAllChapters(chaptersDir, { onlyNewChapters: true });
  } else if (args.length === 1) {
    // Alternative mode: process only new/modified chapters in the specified directory
    const chaptersDir = args[0];
    processAllChapters(chaptersDir, { onlyNewChapters: true });
  } else if (args.length === 2 && args[0] === '--all') {
    // Process all chapters mode (force update)
    const chaptersDir = args[1];
    processAllChapters(chaptersDir, { onlyNewChapters: false });
  } else if (args.length === 2 && args[0] !== '--all') {
    // Legacy mode: process a single chapter
    const [texFile, title] = args;
    processChapter({ texFile, title, forceUpdate: true });
  } else {
    console.error(`
Usage: 
  ts-node process-chapter.ts                      # Process only new/modified chapters in default 'chapters' directory
  ts-node process-chapter.ts <chapters-directory> # Process only new/modified chapters in specified directory
  ts-node process-chapter.ts --all <chapters-directory> # Process all chapters (force update)
  ts-node process-chapter.ts <tex-file> <title>   # Process a single chapter
`);
    process.exit(1);
  }
}