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
    "title": "Calculus",
    "href": "/calculus"
  },
  {
    "title": "Complex Analysis",
    "href": "/complex_analysis"
  },
  {
    "title": "Covariance Contravariance",
    "href": "/covariance_contravariance"
  },
  {
    "title": "Covariant Derivative Connection",
    "href": "/covariant_derivative_connection"
  },
  {
    "title": "Distributions",
    "href": "/distributions"
  },
  {
    "title": "Dynamical Systems",
    "href": "/dynamical_systems"
  },
  {
    "title": "Fiber Bundles",
    "href": "/fiber_bundles"
  },
  {
    "title": "Gaussian Integrals",
    "href": "/gaussian_integrals"
  },
  {
    "title": "Generating Functions",
    "href": "/generating_functions"
  },
  {
    "title": "Greens Equations",
    "href": "/greens_equations"
  },
  {
    "title": "Hilbert Spaces",
    "href": "/hilbert_spaces"
  },
  {
    "title": "Information Theory",
    "href": "/information_theory"
  },
  {
    "title": "Lie Group And Lie Algebra",
    "href": "/lie_group_and_lie_algebra"
  },
  {
    "title": "Lorentz Group",
    "href": "/lorentz_group"
  },
  {
    "title": "Manifolds",
    "href": "/manifolds"
  },
  {
    "title": "Math Basics",
    "href": "/math_basics"
  },
  {
    "title": "Mathematical Transforms",
    "href": "/mathematical_transforms"
  },
  {
    "title": "Multidimensional Optimization",
    "href": "/multidimensional_optimization"
  },
  {
    "title": "Newton Raphson",
    "href": "/newton_raphson"
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
