import os
import sys
import pypandoc
import re
import shutil
import glob
from pathlib import Path
import subprocess
import tempfile
import uuid

def escape_braces(content):
    """Escape curly braces in math environments."""
    content = re.sub(r'(?<!\\)\{', '\\{', content)
    content = re.sub(r'(?<!\\)\}', '\\}', content)
    return content

def remove_language_references(content):
    """Remove language references in code blocks."""
    return re.sub(r'``` \{\.([a-zA-Z]+)\s+language="[^"]+"\}', '```', content)

def clean_code_blocks(content):
    """Clean up code block formatting."""
    def clean_block(match):
        code = match.group(1).strip()

        code = re.sub(r'\{\.([a-zA-Z]+)\s+language="[^"]+"\}', '', code)
        return f'```\n{code}\n```'
    
    return re.sub(r'```([\s\S]*?)```', clean_block, content)

def fix_math_delimiters(content):
    """Convert \( \) to $ $ for inline math and ensure proper display math formatting."""
    content = re.sub(r'\\\((.*?)\\\)', r'$\1$', content)
    
    return content

def fix_set_notation(content):
    """Fix set notation formatting."""
    content = re.sub(r'\\\\{\\\\}', '\\{\\}', content)
    content = re.sub(r'\\\\{([^}]*)\\\\}', '\\{\\1\\}', content)
    return content

def format_tables(content):
    """Format tables in the desired style."""
    def format_table(match):
        table_content = match.group(1)
        
        lines = [line.strip() for line in table_content.split('\n') if line.strip()]
        
        table_content = '\n'.join(lines)
        table_content = re.sub(r'\{\}', '&#123;&#125;', table_content)
        
        formatted_lines = []
        for line in lines:
            if '----' in line:
                continue
            parts = line.split('$', 2)
            if len(parts) >= 2:
                property_name = parts[0].strip()
                definition = '$' + '$'.join(parts[1:])
                formatted_lines.append(f'| {property_name} | {definition} |')
        
        table = "| Property | Definition |\n|-------------|---------------|\n"
        table += '\n'.join(formatted_lines)
        
        return table
    
    content = re.sub(r'::: center\n(.*?)\n:::', format_table, content, flags=re.DOTALL)
    return content

def remove_labels(content):
    """Remove LaTeX label tags and references."""
    content = re.sub(r'\\label\{[^}]*\}', '', content)
    content = re.sub(r'\{#[^}]*\}', '', content)
    content = re.sub(r'\{reference-type="[^"]*"\s+reference="[^"]*"\}', '', content)
    content = re.sub(r'\[\[.*?\]\]\(#.*?\)', '', content)
    content = re.sub(r'#\s+([^\\]+)\\', r'# \1', content)
    content = re.sub(r'\[\]\s*\n', '\n', content)
    content = re.sub(r'Table \[\[.*?\]\]', 'Table', content)
    content = re.sub(r'\(#.*?\)', '', content)
    content = re.sub(r'\[\[.*?\]\]', '', content)
    content = re.sub(r'\n\s*\n\s*\n', '\n\n', content)
    return content

def add_frontmatter(content, title):
    """Add YAML frontmatter to the content."""
    frontmatter = f"""---
    title: "{title}"
    description: "{title}"
    ---

    """
    return frontmatter + content

def extract_title(tex_content):
    """Extract title from LaTeX content."""
    chapter_match = re.search(r'\\chapter\{([^}]*)\}', tex_content)
    title_match = re.search(r'\\title\{([^}]*)\}', tex_content)
    return chapter_match.group(1) if chapter_match else (title_match.group(1) if title_match else "Untitled")

def extract_and_render_tikz(content, tex_file_path, output_dir):
    """Extract TikZ diagrams from the LaTeX source and render them as images."""
    # Get the chapter name for organizing TikZ images in public directory
    chapter_name = os.path.splitext(os.path.basename(tex_file_path))[0]
    
    project_root = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__))))
    public_figures_dir = os.path.join(project_root, 'public', 'figures', chapter_name)
    
    # Create directory if it doesn't exist
    if not os.path.exists(public_figures_dir):
        os.makedirs(public_figures_dir)
    
    # Get the directory of the tex file for includes
    tex_dir = os.path.dirname(os.path.abspath(tex_file_path))
    
    # Find all TikZ picture environments
    tikz_pattern = r'\\begin\{tikzpicture\}(.*?)\\end\{tikzpicture\}'
    tikz_matches = re.finditer(tikz_pattern, content, re.DOTALL)
    
    # Template for standalone LaTeX document with TikZ
    tikz_template = r"""\documentclass[tikz,border=3mm]{standalone}
\usepackage{tikz}
\usetikzlibrary{arrows,shapes,positioning,calc,decorations.pathreplacing,decorations.pathmorphing,decorations.markings}
%ADDITIONAL_PACKAGES%
\begin{document}
\begin{tikzpicture}
%TIKZ_CONTENT%
\end{tikzpicture}
\end{document}
"""
    
    # Process each TikZ diagram
    for i, match in enumerate(tikz_matches):
        tikz_content = match.group(1)
        
        # Create a unique name for the output file
        unique_id = str(uuid.uuid4())[:8]
        output_filename = f"tikz_{i}_{unique_id}.png"
        output_path = os.path.join(public_figures_dir, output_filename)
        
        try:
            # Create a temporary directory for LaTeX compilation
            with tempfile.TemporaryDirectory() as temp_dir:
                # Prepare the standalone LaTeX file with the TikZ content
                tikz_document = tikz_template.replace('%TIKZ_CONTENT%', tikz_content)
                
                # Try to extract additional packages needed from the original file
                packages = re.findall(r'\\usepackage(\[.*?\])?\{(.*?)\}', content)
                additional_packages = "\n".join([f"\\usepackage{opt}{{{pkg}}}" for opt, pkg in packages])
                tikz_document = tikz_document.replace('%ADDITIONAL_PACKAGES%', additional_packages)
                
                # Write the temporary LaTeX file
                temp_tex_file = os.path.join(temp_dir, 'tikz_temp.tex')
                with open(temp_tex_file, 'w') as f:
                    f.write(tikz_document)
                
                # Compile with pdflatex
                subprocess.run(['pdflatex', '-interaction=nonstopmode', '-output-directory', temp_dir, temp_tex_file], 
                               check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
                # Convert PDF to PNG with higher resolution
                pdf_path = os.path.join(temp_dir, 'tikz_temp.pdf')
                if os.path.exists(pdf_path):
                    subprocess.run(['convert', '-density', '300', pdf_path, '-quality', '90', output_path],
                                  check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                else:
                    raise Exception("PDF output not generated")
                
                # Replace the TikZ environment with an image tag in the content
                img_tag = f'<img src="/figures/{chapter_name}/{output_filename}" alt="TikZ diagram" />'
                content = content.replace(match.group(0), img_tag)
            
        except Exception as e:
            print(f"Error rendering TikZ diagram: {e}")
            # Keep the original TikZ code as a code block
            content = content.replace(match.group(0), f"```\n{match.group(0)}\n```")
    
    return content

def handle_images(content, tex_file_path, output_dir):
    """Process LaTeX image references and copy images to output directory."""
    # Instead of creating a new images directory, use the public/figures path
    # The images should already be in public/figures
    # Get the directory of the tex file
    tex_dir = os.path.dirname(os.path.abspath(tex_file_path))
    
    # Get the chapter name from the tex file
    chapter_name = os.path.splitext(os.path.basename(tex_file_path))[0]
    
    # Handle includegraphics commands
    def process_image(match):
        options = match.group(2) if match.group(2) else ""
        image_path = match.group(3)
        after_content = match.group(4) if len(match.groups()) > 3 and match.group(4) else ""
        
        # Remove file extension if present, as LaTeX allows specifying images without extensions
        image_basename = os.path.splitext(image_path)[0]
        
        # Extract width if specified in options - but don't convert to style
        width_attr = ""
        width_match = re.search(r'width=([^,\]]+)', options)
        if width_match:
            # Don't convert to CSS, leave the width attribute to be handled by MDX renderer
            pass
        
        # Use the Next.js public directory URL structure
        # Ensure the path starts with a forward slash
        relative_path = f'/figures/{chapter_name}/{os.path.basename(image_basename)}.png'
        
        # Extract caption if present
        caption_match = re.search(r'\\caption\{([^}]*)\}', after_content)
        caption = caption_match.group(1) if caption_match else ""
        
        if caption:
            return f'<figure>\n  <img src="{relative_path}" alt="{caption}" />\n  <figcaption>{caption}</figcaption>\n</figure>'
        else:
            return f'<img src="{relative_path}" alt="Figure" />'
    
    # Handle \includegraphics commands
    content = re.sub(r'\\includegraphics(\[([^\]]*)\])?\{([^}]*)\}(.*?)(?=\\|$)', process_image, content)
    
    # Handle figure environments
    def process_figure(match):
        figure_content = match.group(1)
        
        # Extract the includegraphics command
        img_match = re.search(r'\\includegraphics(\[([^\]]*)\])?\{([^}]*)\}(.*?)(?=\\|$)', figure_content)
        if img_match:
            options = img_match.group(2) if img_match.group(2) else ""
            image_path = img_match.group(3)
            
            # Extract caption if present
            caption_match = re.search(r'\\caption\{([^}]*)\}', figure_content)
            caption = caption_match.group(1) if caption_match else ""
            
            # Process the image in the same way as above
            result = process_image(img_match)
            
            # If there was no caption in the includegraphics match but there is one in the figure environment
            if caption and '<figcaption>' not in result:
                if '<figure>' in result:
                    # Replace the existing figcaption
                    result = re.sub(r'<figcaption>.*?</figcaption>', f'<figcaption>{caption}</figcaption>', result)
                else:
                    # Convert to figure with caption
                    result = result.replace('<img', '<figure>\n  <img')
                    result = result.replace('/>', f'/>\n  <figcaption>{caption}</figcaption>\n</figure>')
            
            return result
        return match.group(0)
    
    content = re.sub(r'\\begin\{figure\}(.*?)\\end\{figure\}', process_figure, content, flags=re.DOTALL)
    
    return content

def handle_subfigures(content, tex_file_path, output_dir):
    """Handle LaTeX subfigures by converting them to MDX image grids."""
    # Get the chapter name for image paths
    chapter_name = os.path.splitext(os.path.basename(tex_file_path))[0]
    
    # Get the directory of the tex file
    tex_dir = os.path.dirname(os.path.abspath(tex_file_path))
    
    def process_subfigure_environment(match):
        """Process a full subfigure environment and convert to MDX grid."""
        figure_env = match.group(0)
        figure_content = match.group(1)
        
        # Extract the main figure caption if present
        main_caption_match = re.search(r'\\caption\{([^}]*)\}', figure_content)
        main_caption = main_caption_match.group(1) if main_caption_match else ""
        
        # Find all subfigures
        subfigure_pattern = r'\\begin\{subfigure\}(?:\[.*?\])?\{.*?\}(.*?)\\end\{subfigure\}'
        subfigures = re.finditer(subfigure_pattern, figure_content, re.DOTALL)
        
        subfigure_images = []
        for subfig in subfigures:
            subfig_content = subfig.group(1)
            
            # Extract subfigure caption
            subcaption_match = re.search(r'\\caption\{([^}]*)\}', subfig_content)
            subcaption = subcaption_match.group(1) if subcaption_match else ""
            
            # Extract image
            img_match = re.search(r'\\includegraphics(?:\[([^\]]*)\])?\{([^}]*)\}', subfig_content)
            if img_match:
                options = img_match.group(1) if img_match.group(1) else ""
                image_path = img_match.group(2)
                
                # Process image to get the path in public directory
                image_basename = os.path.splitext(image_path)[0]
                
                # Create the public URL path - ensure it starts with a slash
                public_path = f'/figures/{chapter_name}/{os.path.basename(image_basename)}.png'
                
                # Add to our list of subfigure images
                subfigure_images.append({
                    'path': public_path,
                    'caption': subcaption
                })
        
        # Create a grid of images based on the number of subfigures
        if subfigure_images:
            num_images = len(subfigure_images)
            
            # Determine grid layout (auto, or get from figure options if available)
            columns = min(3, num_images)  # Default to max 3 columns
            
            # Create the grid container - without inline styles
            grid_html = f'<figure className="subfigure-grid">\n'
            grid_html += f'  <div className="grid-container">\n'
            
            # Add each subfigure
            for img in subfigure_images:
                if img['path']:
                    grid_html += f'    <div className="subfigure">\n'
                    grid_html += f'      <img src="{img["path"]}" alt="{img["caption"]}" />\n'
                    if img['caption']:
                        grid_html += f'      <figcaption>{img["caption"]}</figcaption>\n'
                    grid_html += f'    </div>\n'
                else:
                    grid_html += f'    <div>[Missing Image: {img["caption"]}]</div>\n'
            
            grid_html += '  </div>\n'
            
            # Add main caption if present
            if main_caption:
                grid_html += f'  <figcaption>{main_caption}</figcaption>\n'
            
            grid_html += '</figure>'
            
            return grid_html
        
        # If no subfigures were found, return the original content
        return match.group(0)
    
    # Find figure environments containing subfigures
    subfigure_pattern = r'\\begin\{figure\}(.*?\\begin\{subfigure\}.*?\\end\{subfigure\}.*?)\\end\{figure\}'
    content = re.sub(subfigure_pattern, process_subfigure_environment, content, flags=re.DOTALL)
    
    return content

def ensure_image_paths(content):
    """Ensure all image paths in the MDX content have the correct format."""
    # Fix any image src that might not have a leading slash in HTML tags
    content = re.sub(r'<img src="(?!\/|http)([^"]+)"', r'<img src="/\1"', content)
    
    # Fix any image paths in Markdown format ![alt](path) 
    content = re.sub(r'!\[(.*?)\]\((?!\/|http)([^)]+)\)', r'![\1](/\2)', content)
    
    # Also handle Markdown format with attributes ![alt](path){width="x"} 
    content = re.sub(r'!\[(.*?)\]\((?!\/|http)([^)]+)\)(\{[^}]*\})', r'![\1](/\2)\3', content)
    
    # Convert any Markdown images to the chapter-specific path format
    chapter_name = os.environ.get('CURRENT_CHAPTER_NAME', '')
    if chapter_name:
        # Handle paths that aren't already in the /figures/chapter structure
        def fix_paths(match):
            alt_text = match.group(1)
            path = match.group(2)
            attrs = match.group(3) if len(match.groups()) > 2 else ''
            
            # Skip if already in correct format
            if re.match(r'^/figures/[^/]+/', path):
                return f'![{alt_text}]({path}){attrs}'
            
            # Extract filename from path
            filename = os.path.basename(path)
            # Create new path in chapter figures directory
            new_path = f'/figures/{chapter_name}/{filename}'
            return f'![{alt_text}]({new_path}){attrs}'
        
        # Apply the path fixing to Markdown images
        content = re.sub(r'!\[(.*?)\]\(([^)]+)\)(\{[^}]*\})?', fix_paths, content)
        
        # Handle the specific pattern with figures/part1b/... paths
        # Specifically target the pattern shown in the example
        content = re.sub(r'!\[(.*?)\]\(figures/part1b/[^)]+/([^/)]+)\)(\{[^}]*\})?', 
                         lambda m: f'![{m.group(1)}](/figures/{chapter_name}/{m.group(2)}){m.group(3) if m.group(3) else ""}', 
                         content)
    
    # Check and fix any malformed paths (double slashes, etc.)
    content = re.sub(r'src="//+', r'src="/', content)
    content = re.sub(r'\]\(//+', r'](/', content)
    
    return content

def remove_inline_styles(content):
    """Remove inline style attributes from HTML tags in the MDX content."""
    # Remove style attribute from img tags - handle various formats
    content = re.sub(r'<img([^>]*)style=\{[^}]*\}([^>]*)>', r'<img\1\2>', content)
    content = re.sub(r'<img([^>]*)style\s*=\s*\{[^}]*\}([^>]*)>', r'<img\1\2>', content)
    
    # Handle the specific format: style={ width: "40%" }
    content = re.sub(r'<img([^>]*)style=\{\s*width:\s*"[^"]*"\s*\}([^>]*)>', r'<img\1\2>', content)
    
    # More general case with spaces and different attribute formats
    content = re.sub(r'<img([^>]*)\bstyle\s*=\s*\{\s*[^}]*\s*\}([^>]*)>', r'<img\1\2>', content)
    
    # Remove style attribute from other tags
    content = re.sub(r'<(\w+)([^>]*)\bstyle\s*=\s*\{[^}]*\}([^>]*)>', r'<\1\2\3>', content)
    
    # Clean up any double spaces or trailing/leading spaces in tag attributes
    content = re.sub(r'<(\w+)([^>]*)  +([^>]*)>', r'<\1\2 \3>', content)
    content = re.sub(r'<(\w+)([^>]*) +>', r'<\1\2>', content)
    
    # Fix markdown image style attributes as well - including width="x" format
    content = re.sub(r'!\[(.*?)\]\((.*?)\)(\{[^}]*\})', r'![\1](\2)', content)
    content = re.sub(r'!\[(.*?)\]\((.*?)\)(\{width="[^"]*"\})', r'![\1](\2)', content)
    
    # Handle the special case with None{width="2in"} format
    content = re.sub(r'(!\[[^\]]*\]\([^)]*\))None\{width="[^"]*"\}', r'\1', content)
    
    return content

def convert_tex_to_mdx(tex_file, output_dir):
    """Convert LaTeX file to MDX format."""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    try:
        with open(tex_file, 'r') as file:
            content = file.read()

        # Set environment variable for current chapter name for path fixing
        chapter_name = os.path.splitext(os.path.basename(tex_file))[0]
        os.environ['CURRENT_CHAPTER_NAME'] = chapter_name
        
        title = extract_title(content)
        
        # Process subfigures first, they're more complex
        content = handle_subfigures(content, tex_file, output_dir)
        
        # Process TikZ diagrams before conversion
        content = extract_and_render_tikz(content, tex_file, output_dir)

        md_content = pypandoc.convert_text(content, 'markdown', format='latex')

        mdx_content = escape_braces(md_content)
        mdx_content = remove_language_references(mdx_content)

        mdx_content = clean_code_blocks(mdx_content)
        mdx_content = fix_set_notation(mdx_content)
        mdx_content = fix_math_delimiters(mdx_content)
        mdx_content = format_tables(mdx_content)
        mdx_content = remove_labels(mdx_content)
        
        # Handle regular images
        mdx_content = handle_images(mdx_content, tex_file, output_dir)
        
        # Ensure all image paths are correct
        mdx_content = ensure_image_paths(mdx_content)
        
        # Remove any inline styles from HTML tags
        mdx_content = remove_inline_styles(mdx_content)
        
        mdx_content = add_frontmatter(mdx_content, title)

        mdx_file = os.path.join(output_dir, 'index.mdx')
        with open(mdx_file, 'w') as file:
            file.write(mdx_content)

        print(f"Successfully converted {tex_file} to {mdx_file}")
        print(f"Title: {title}")

    except Exception as e:
        print(f"Error converting {tex_file}: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Clean up environment variable
        if 'CURRENT_CHAPTER_NAME' in os.environ:
            del os.environ['CURRENT_CHAPTER_NAME']

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python covert_tex_to_md.py <input_tex_file> <output_directory>")
        sys.exit(1)

    tex_file = sys.argv[1]
    output_dir = sys.argv[2]
    convert_tex_to_mdx(tex_file, output_dir)