import path from 'path';
import fs from 'fs';
import { exec } from 'child_process';
import { promisify } from 'util';
import { ROUTES, EachRoute } from '../lib/routes-config';

const execAsync = promisify(exec);

interface ProcessChapterOptions {
  texFile: string;
  title: string;
}

async function updateRoutesConfig(title: string, href: string) {
  // Find or create the Chapters route
  let chaptersRoute = ROUTES.find(route => route.title === "Chapters");
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
  const chapterExists = chaptersRoute.items.some(item => item.href === href);
  if (!chapterExists) {
    chaptersRoute.items.push({
      title,
      href,
    });

    // Sort chapters alphabetically by title
    chaptersRoute.items.sort((a, b) => {
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
    console.log('Converting TEX to MDX...');
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
  } catch (error) {
    console.error('Error processing chapter:', error);
    process.exit(1);
  }
}

if (require.main === module) {
  const args = process.argv.slice(2);
  if (args.length !== 2) {
    console.error('Usage: ts-node process-chapter.ts <tex-file> <chapter-title>');
    process.exit(1);
  }

  const [texFile, title] = args;
  processChapter({ texFile, title });
} 