"use client";

import { PropsWithChildren, useEffect } from "react";

declare global {
  interface Window {
    katex: any;
    renderMathInElement: any;
  }
}

export function Typography({ children }: PropsWithChildren) {
  useEffect(() => {
    // Load KaTeX auto-render
    const script = document.createElement('script');
    script.src = "https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9/contrib/auto-render.min.js";
    script.async = true;
    script.onload = () => {
      // After loading auto-render, render math in the container
      if (window.renderMathInElement) {
        window.renderMathInElement(document.querySelector('.math-content'), {
          delimiters: [
            {left: '$$', right: '$$', display: true},
            {left: '$', right: '$', display: false},
          ],
          throwOnError: false
        });
      }
    };
    document.head.appendChild(script);

    return () => {
      document.head.removeChild(script);
    };
  }, [children]);

  return (
    <>
      {/* KaTeX CSS */}
      <link
        rel="stylesheet"
        href="https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9/katex.min.css"
      />
      
      {/* KaTeX JS */}
      <script 
        src="https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9/katex.min.js"
        async
      />
      
      <div className="prose prose-zinc dark:prose-invert prose-code:font-code dark:prose-code:bg-neutral-900 dark:prose-pre:bg-neutral-900 prose-code:bg-neutral-100 prose-pre:bg-neutral-100 prose-headings:scroll-m-20 w-[85vw] sm:w-full sm:mx-auto prose-code:text-sm prose-code:leading-6 dark:prose-code:text-white prose-code:text-neutral-800 prose-code:p-1 prose-code:rounded-md prose-pre:border pt-2 prose-code:before:content-none prose-code:after:content-none !min-w-full prose-img:rounded-md prose-img:border">
        <div className="math-content">
          {children}
        </div>
      </div>
    </>
  );
}

export default Typography;