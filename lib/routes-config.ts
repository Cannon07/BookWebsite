export type EachRoute = {
  title: string;
  href: string;
  noLink?: true;
  items?: EachRoute[];
};

export const ROUTES: EachRoute[] = [
  {
    title: "Chapters",
    href: "/output_mdx",
    noLink: true,
    items: [
      { title: "Introduction", href: "/intro/intro" },
      {
        title: "Outtakes",
        href: "/Outtakes",
        noLink: true,
        items: [
          { title: "Condensed Matter", href: "/condensed_matter" },
          { title: "Intro Outtakes", href: "/intro_outtakes" },
          { 
            title: "Numerical Methods", 
            href: "/NumericalMethods",
            noLink: true,
            items: [
              { title: "Bracketing And Bisection", href: "/bracketing_and_bisection" },
              { title: "Data Interpolation", href: "/data_interpolation" },
              { title: "Errors and False Position", href: "/errors_and_false_position" },
              { title: "Golden Section", href: "/golden_section" },
              { title: "Linear Analytical", href: "/linear_analytical" },
              { title: "Linear Least Squares", href: "/linear_least_squares" },
              { title: "Linear Least Squares Cont.", href: "/linear_least_squares_cont" },
              { title: "Numerical Integration", href: "/numerical_integration" },
              { title: "Numerical ODEs", href: "/numerical_odes" },
              { title: "Parabolic Interpolation", href: "/parabolic_interpolation" },
            ]
          },
          { title: "Photosynthesis", href: "/photosynthesis" },
          { 
            title: "Statistical Mechanics", 
            href: "/StatisticalMechanics", 
            noLink: true,
            items: [
              { title: "Mixtures", href: "/Mixtures" },
            ]
          },
          { title: "Transfer Matrix", href: "/transfer_matrix" },
          { title: "Water", href: "/water" },
        ],
      },
    ],
  }, 
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
