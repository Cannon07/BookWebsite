export type EachRoute = {
      title: string;
      href: string;
      noLink?: true;
      items?: EachRoute[];
    };
    export const ROUTES: EachRoute[] = [
  {
    "title": "Chapters",
    "href": "/chapters",
    "noLink": true,
    "items": [
      {
        "title": "Introduction",
        "href": "/introduction"
      },
      {
        "title": "Kernel Methods",
        "href": "/kernel_methods"
      },
      {
        "title": "What is Differentiable Physics?",
        "href": "/gaussian_process"
      }
    ]
  }
];
    type Page = { title: string; href: string };
    function getRecurrsiveAllLinks(node: EachRoute) {
      const ans: Page[] = [];
      if (!node.noLink) {
        ans.push({ title: node.title, href: node.href });
      }
      node.items?.forEach((subNode) => {
        const temp = { ...subNode, href: `${node.href}${subNode.href}` };
        ans.push(...getRecurrsiveAllLinks(temp));
      });
      return ans;
    }
    export const page_routes = ROUTES.map((it) => getRecurrsiveAllLinks(it)).flat();
    