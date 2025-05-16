"use client";
import { PropsWithChildren, useEffect, useRef } from "react";

declare global {
  interface Window {
    katex: any;
    renderMathInElement: any;
  }
}

export function Typography({ children }: PropsWithChildren) {
  const contentRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Load KaTeX library
    const loadKaTeX = async () => {
      // Check if KaTeX is already loaded
      if (window.renderMathInElement) {
        renderMath();
        return;
      }

      // Load KaTeX CSS
      if (!document.querySelector('link[href*="katex.min.css"]')) {
        const link = document.createElement('link');
        link.rel = 'stylesheet';
        link.href = 'https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9/katex.min.css';
        document.head.appendChild(link);
      }

      // Load KaTeX JS
      if (!window.katex) {
        const script = document.createElement('script');
        script.src = 'https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9/katex.min.js';
        script.async = true;
        await new Promise((resolve) => {
          script.onload = resolve;
          document.head.appendChild(script);
        });
      }

      // Load auto-render extension
      if (!window.renderMathInElement) {
        const script = document.createElement('script');
        script.src = 'https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9/contrib/auto-render.min.js';
        script.async = true;
        await new Promise((resolve) => {
          script.onload = resolve;
          document.head.appendChild(script);
        });
      }

      renderMath();
    };

    // Render math using KaTeX
    const renderMath = () => {
      if (contentRef.current && window.renderMathInElement) {
        try {
          window.renderMathInElement(contentRef.current, {
            delimiters: [
              { left: '$$', right: '$$', display: true },
              { left: '$', right: '$', display: false },
            ],
            throwOnError: false,
            errorColor: '#FF6666',
            macros: {
              // Add common LaTeX macros that might be in your content
              "\\R": "\\mathbb{R}",
              "\\N": "\\mathbb{N}",
              "\\Z": "\\mathbb{Z}",
              "\\Q": "\\mathbb{Q}"
            },
            trust: true
          });
        } catch (error) {
          console.error('Error rendering math:', error);
        }
      }
    };

    loadKaTeX();

    // Add a MutationObserver to handle dynamic content updates
    if (contentRef.current) {
      const observer = new MutationObserver(() => {
        if (window.renderMathInElement) {
          renderMath();
        }
      });
      
      observer.observe(contentRef.current, {
        childList: true,
        subtree: true
      });
      
      return () => observer.disconnect();
    }
  }, [children]);

  return (
    <div className="prose prose-zinc dark:prose-invert prose-code:font-code 
                    dark:prose-code:bg-neutral-900 dark:prose-pre:bg-neutral-900 
                    prose-code:bg-neutral-100 prose-pre:bg-neutral-100 
                    prose-headings:scroll-m-20 w-[85vw] sm:w-full sm:mx-auto 
                    prose-code:text-sm prose-code:leading-6 dark:prose-code:text-white 
                    prose-code:text-neutral-800 prose-code:p-1 prose-code:rounded-md 
                    prose-pre:border pt-2 prose-code:before:content-none 
                    prose-code:after:content-none !min-w-full prose-img:rounded-md prose-img:border">
      <div className="math-content" ref={contentRef}>
        {children}
      </div>
    </div>
  );
}