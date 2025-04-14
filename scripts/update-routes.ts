import fs from 'fs';
import path from 'path';
import { ROUTES, EachRoute } from '../lib/routes-config';

interface ChapterInfo {
  title: string;
  href: string;
}

export function updateRoutes(newChapter: ChapterInfo): void {
  // Find the Chapters route in the configuration
  const chaptersRoute = ROUTES.find(route => route.title === "Chapters");
  
  if (!chaptersRoute) {
    throw new Error("Chapters route not found in configuration");
  }

  // Add the new chapter to the items array
  if (!chaptersRoute.items) {
    chaptersRoute.items = [];
  }

  // Check if chapter already exists
  const chapterExists = chaptersRoute.items.some(
    item => item.href === newChapter.href
  );

  if (!chapterExists) {
    chaptersRoute.items.push({
      title: newChapter.title,
      href: newChapter.href,
    });

    // Sort chapters alphabetically by title
    chaptersRoute.items.sort((a, b) => a.title.localeCompare(b.title));

    // Convert the updated routes to a string
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

// If running directly (not imported)
if (require.main === module) {
  const args = process.argv.slice(2);
  if (args.length !== 2) {
    console.error('Usage: ts-node update-routes.ts <chapter-title> <chapter-href>');
    process.exit(1);
  }

  const [title, href] = args;
  updateRoutes({ title, href });
  console.log(`Updated routes with new chapter: ${title}`);
} 