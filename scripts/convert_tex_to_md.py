import os
import sys
import traceback
import pypandoc
import re
import shutil
import glob
from pathlib import Path
import subprocess
import tempfile
import uuid

def get_base_path():
    """Extract basePath from next.config.mjs"""
    try:
        project_root = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
        next_config_path = os.path.join(project_root, 'next.config.mjs')
        
        with open(next_config_path, 'r') as f:
            config_content = f.read()
            
        # Extract basePath using regex
        base_path_match = re.search(r'basePath:\s*([^,\n]+)', config_content)
        if base_path_match:
            base_path = base_path_match.group(1).strip()
            
            # Handle the conditional expression
            if 'isProduction' in base_path:
                # Use the production value since we're generating static files
                production_path_match = re.search(r'"([^"]*)"', base_path)
                if production_path_match:
                    return production_path_match.group(1)
            else:
                # Remove quotes if present
                return base_path.strip('"\'')
    except Exception as e:
        print(f"Warning: Could not extract basePath from next.config.mjs: {e}")
    
    return ''  # Default to empty string if not found

# Get the basePath early
BASE_PATH = get_base_path()

def fix_code_blocks_with_math(content):
    """
    Convert LaTeX-style code blocks with embedded math to standard markdown
    code blocks with text replacements for math symbols.
    """
    def process_code_block(match):
        # Extract the language and code content
        lang_match = re.search(r'\\{\.([a-zA-Z0-9_]+)\s+language="([^"]+)"\}', match.group(1))
        language = lang_match.group(2) if lang_match else "text"
        
        # Get the code content
        code_content = match.group(2)
        
        # Replace common math symbols with text equivalents
        math_replacements = {
            r'\$\\to\$': '->',         # Function arrow
            r'\$\\rightarrow\$': '->',  # Right arrow
            r'\$\\leftarrow\$': '<-',   # Left arrow
            r'\$\\alpha\$': 'alpha',    # Greek letter alpha
            r'\$\\beta\$': 'beta',      # Greek letter beta
            # Add more replacements as needed
        }
        
        for math_pattern, replacement in math_replacements.items():
            code_content = re.sub(math_pattern, replacement, code_content)
        
        # Also try to find any remaining math delimiters and handle them
        code_content = re.sub(r'\$([^$]+)\$', lambda m: m.group(1), code_content)
        
        # Format as a standard markdown code block
        return f"```{language}\n{code_content.strip()}\n```"
    
    # Match LaTeX-style code blocks: ```{.lang language="lang"} code ```
    pattern = r'```\s*(\\{\.[\w]+\s+language="[^"]+"\})\s*([\s\S]*?)```'
    content = re.sub(pattern, process_code_block, content)
    
    return content

def escape_braces(content):
    """Escape curly braces in math environments."""
    content = re.sub(r'(?<!\\)\{', '\\{', content)
    content = re.sub(r'(?<!\\)\}', '\\}', content)
    return content

def replace_latex_code_blocks_with_images(content, code_blocks, rendered_blocks, chapter_name):
    """Replace LaTeX code blocks with image references after all other processing."""
    # Create a mapping from original content to replacements
    replacements = {}
    
    for block in rendered_blocks:
        if 'img_path' in block:
            # Create the clean image tag - no backslashes, no None
            img_tag = f'![image](/code-blocks/{chapter_name}/{block["img_path"]})'
            replacements[block['original']] = img_tag
        elif 'fallback_html' in block:
            replacements[block['original']] = block['fallback_html']
    
    # Replace all occurrences in the content
    for original, replacement in replacements.items():
        content = content.replace(original, replacement)
    
    # Clean up any markdown syntax that might have been escaped
    content = content.replace('\\![', '![')
    content = content.replace('\\]', ']')
    content = content.replace('\\(', '(')
    content = content.replace('\\)', ')')
    
    # Remove any "None" that appear at the end of image tags
    content = re.sub(r'(!\[image\]\(/code-blocks/[^)]+\))None', r'\1', content)
    
    return content

def render_code_blocks_with_images(content, tex_file_path, output_dir):
    """Process all code blocks with LaTeX and render them as transparent images."""
    try:
        # Try to import pdf2image
        import pdf2image
    except ImportError:
        print("pdf2image library not installed. Please install it with:")
        print("pip install pdf2image")
        print("Also ensure you have poppler installed")
        print("Falling back to code block formatting without images.")
        return format_latex_code_blocks(content)
    
    # Get the chapter name for organizing images
    chapter_name = os.path.splitext(os.path.basename(tex_file_path))[0]
    
    # Create path for image files
    project_root = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    img_dir = os.path.join(project_root, 'public', 'code-blocks', chapter_name)
    
    # Ensure directory exists
    if not os.path.exists(img_dir):
        os.makedirs(img_dir)
    
    # Extract code blocks that contain LaTeX
    code_blocks = extract_code_blocks_with_latex(content)
    
    if not code_blocks:
        # No LaTeX code blocks found
        return content
    
    # Render each code block
    rendered_blocks = []
    for i, block in enumerate(code_blocks):
        print(f"Rendering code block {i+1}: {block['content'][:50]}...")
        
        # Try with transparency
        rendered = render_code_block_with_transparency(block, img_dir, i)
        
        if rendered and 'img_path' in rendered:
            rendered_blocks.append(rendered)
            print(f"Successfully rendered code block {i+1} with transparency")
        else:
            print(f"Using fallback for code block {i+1}")
            
            # Use a fallback: format the code block specially
            fallback_html = f"""<div className="code-block-with-latex">
<pre><code className="language-python">
{block['content']}
</code></pre>
</div>"""
            
            rendered_blocks.append({
                'original': block['original'],
                'fallback_html': fallback_html,
                'start': block['start'],
                'end': block['end']
            })
    
    # Replace code blocks in reverse order
    rendered_blocks.sort(key=lambda x: x['start'], reverse=True)
    
    for block in rendered_blocks:
        if 'img_path' in block:
            # Create the image tag using Markdown syntax
            img_tag = f'![image]({BASE_PATH}/code-blocks/{chapter_name}/{block["img_path"]})'
            
            # Replace the original code block
            content = content[:block['start']] + img_tag + content[block['end']:]
        elif 'fallback_html' in block:
            # Use the fallback HTML
            content = content[:block['start']] + block['fallback_html'] + content[block['end']:]
    
    return content

def create_transparent_tex_for_code_block(code_block, language=None):
    """Create a LaTeX document for code blocks with transparent background."""
    # Set language option
    language_option = ""
    if language:
        language_option = f"language={language},"
    
    # Clean up the code block
    code_block = code_block.replace("\\", "\\\\")  # Escape backslashes
    code_block = code_block.replace("$\\\\mathbb", "$\\mathbb")
    code_block = code_block.replace("$\\\\nabla", "$\\nabla")
    code_block = code_block.replace("$\\\\alpha", "$\\alpha")
    code_block = code_block.replace("$\\\\epsilon", "$\\epsilon")
    code_block = code_block.replace("$\\\\to", "$\\to")
    code_block = code_block.replace("$\\\\infty", "$\\infty")
    
    # Create a document with transparent background using a different approach
    return r"""\documentclass[border=10pt]{standalone}
\usepackage{amsmath,amssymb}
\usepackage{listings}
\usepackage{xcolor}

% Use black text on white background - we'll invert colors in image processing
\definecolor{codebackground}{RGB}{255, 255, 255}
\definecolor{codetext}{RGB}{0, 0, 0}

\lstset{
  basicstyle=\ttfamily\color{codetext},
  backgroundcolor=\color{codebackground},
  frame=none,
  breaklines=true,
  mathescape=true,
  escapeinside={$}{$},
  """ + language_option + r"""
}

\begin{document}
\begin{lstlisting}
""" + code_block + r"""
\end{lstlisting}
\end{document}
"""

def render_code_block_with_transparency(code_block, output_dir, index):
    """Render a LaTeX code block with fully transparent background."""
    try:
        # Import pdf2image inside the function to ensure it's available
        import pdf2image
        from PIL import Image, ImageOps
    except ImportError:
        print("pdf2image library not installed. Please install it with:")
        print("pip install pdf2image pillow")
        return None

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Create a temporary directory for LaTeX compilation
    with tempfile.TemporaryDirectory() as temp_dir:
        # Check if there's a language specification
        lang_match = re.match(r'\[language=([a-zA-Z]+)\]', code_block['content'])
        if lang_match:
            language = lang_match.group(1)
            # Remove the language tag from the content
            code_block_content = re.sub(r'^\[language=[a-zA-Z]+\]\s*', '', code_block['content'])
        else:
            language = "python"  # Default
            code_block_content = code_block['content']
        
        # Create the transparent LaTeX document
        latex_doc = create_transparent_tex_for_code_block(code_block_content, language)
        
        # Write to a temporary file
        tex_file_path = os.path.join(temp_dir, f"code_block_{index}.tex")
        with open(tex_file_path, "w") as f:
            f.write(latex_doc)
        
        # Also save the LaTeX source for debugging
        debug_tex_path = os.path.join(output_dir, f"debug_code_block_{index}.tex")
        with open(debug_tex_path, "w") as f:
            f.write(latex_doc)
            
        try:
            # Compile to PDF using pdflatex
            process = subprocess.run(
                ["pdflatex", "-interaction=nonstopmode", "-output-directory", temp_dir, tex_file_path],
                check=False,
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Check if PDF was created
            pdf_path = os.path.join(temp_dir, f"code_block_{index}.pdf")
            if not os.path.exists(pdf_path):
                print(f"LaTeX compilation failed for code block {index}.")
                return None
            
            # Generate unique filename for image
            unique_id = str(uuid.uuid4())[:8]
            img_filename = f"code_block_{index}_{unique_id}.png"
            img_path = os.path.join(output_dir, img_filename)
            
            try:
                # Convert PDF to PNG with higher resolution
                images = pdf2image.convert_from_path(
                    pdf_path, 
                    dpi=300,
                    fmt='png'
                )
                
                if images and len(images) > 0:
                    # Get the first page and convert to RGBA mode
                    img = images[0].convert("RGBA")
                    
                    # Create a completely transparent image of the same size
                    transparent_img = Image.new("RGBA", img.size, (0, 0, 0, 0))
                    
                    # Process the image to make all white/light pixels completely transparent
                    # and copy only the text pixels
                    datas = img.getdata()
                    transparent_data = []
                    
                    for item in datas:
                        # Check if pixel is white or very light (background)
                        if item[0] > 230 and item[1] > 230 and item[2] > 230:
                            # Make it completely transparent
                            transparent_data.append((0, 0, 0, 0))
                        else:
                            # For text, use the original color but ensure it's white (negative of the original)
                            # Assuming darker colors are text - invert to make them white
                            r = 255 - item[0]
                            g = 255 - item[1]
                            b = 255 - item[2]
                            transparent_data.append((r, g, b, 255))
                    
                    transparent_img.putdata(transparent_data)
                    
                    # Auto-crop to remove extra transparent space
                    bbox = transparent_img.getbbox()
                    if bbox:
                        # Add padding
                        padding = 10
                        width, height = transparent_img.size
                        crop_box = (
                            max(0, bbox[0] - padding),
                            max(0, bbox[1] - padding),
                            min(width, bbox[2] + padding),
                            min(height, bbox[3] + padding)
                        )
                        cropped_img = transparent_img.crop(crop_box)
                        # Save with transparency
                        cropped_img.save(img_path, 'PNG')
                    else:
                        # If no bounding box (unlikely), save the whole image
                        transparent_img.save(img_path, 'PNG')
                    
                    # Return image info
                    return {
                        'original': code_block['original'],
                        'img_path': img_filename,
                        'start': code_block['start'],
                        'end': code_block['end']
                    }
                else:
                    print(f"No images generated from PDF for code block {index}.")
                    return None
                
            except Exception as convert_error:
                print(f"Error converting PDF to transparent PNG: {convert_error}")
                
                # Try alternative methods if pdf2image fails
                try:
                    # Try with ImageMagick
                    subprocess.run(
                        ["convert", "-density", "300", "-background", "none", 
                         "-fill", "white", "-opaque", "black", 
                         pdf_path, img_path],
                        check=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE
                    )
                    
                    if os.path.exists(img_path):
                        return {
                            'original': code_block['original'],
                            'img_path': img_filename,
                            'start': code_block['start'],
                            'end': code_block['end']
                        }
                except Exception:
                    pass
                
                # Try Ghostscript as a last resort
                try:
                    gs_cmd = [
                        "gs", 
                        "-dSAFER", 
                        "-dBATCH", 
                        "-dNOPAUSE", 
                        "-sDEVICE=pngalpha", 
                        "-dTextAlphaBits=4",
                        "-dGraphicsAlphaBits=4",
                        "-r300",
                        "-sOutputFile=" + img_path,
                        pdf_path
                    ]
                    
                    subprocess.run(gs_cmd, check=True)
                    
                    if os.path.exists(img_path):
                        # Open the image and invert colors (Ghostscript might output with black text)
                        img = Image.open(img_path).convert("RGBA")
                        datas = img.getdata()
                        newData = []
                        
                        for item in datas:
                            # If pixel has any opacity (is visible)
                            if item[3] > 0:
                                # Make it white
                                newData.append((255, 255, 255, item[3]))
                            else:
                                # Keep transparent pixels transparent
                                newData.append((0, 0, 0, 0))
                        
                        img.putdata(newData)
                        img.save(img_path)
                        
                        return {
                            'original': code_block['original'],
                            'img_path': img_filename,
                            'start': code_block['start'],
                            'end': code_block['end']
                        }
                except Exception as gs_error:
                    print(f"Ghostscript conversion failed: {gs_error}")
                    return None
                
        except Exception as e:
            print(f"Error rendering code block {index}: {e}")
            return None

def create_simplified_tex_for_code_block(code_block, language=None):
    """Create a minimal LaTeX document for code blocks to ensure compilation."""
    # Set language option
    language_option = ""
    if language:
        language_option = f"language={language},"
    
    # Clean up the code block to avoid LaTeX issues
    # Replace problematic characters
    code_block = code_block.replace("\\", "\\\\")  # Escape backslashes
    code_block = code_block.replace("$\\\\mathbb", "$\\mathbb")  # Fix double backslash in mathbb
    code_block = code_block.replace("$\\\\nabla", "$\\nabla")  # Fix double backslash in nabla
    code_block = code_block.replace("$\\\\alpha", "$\\alpha")  # Fix double backslash in alpha
    code_block = code_block.replace("$\\\\epsilon", "$\\epsilon")  # Fix double backslash in epsilon
    
    # Create a minimal LaTeX document
    return r"""\documentclass{article}
\usepackage{amsmath,amssymb}
\usepackage{listings}
\usepackage{xcolor}

\definecolor{codebackground}{RGB}{240, 240, 240}
\definecolor{codestring}{RGB}{163, 21, 21}
\definecolor{codekeyword}{RGB}{0, 0, 255}

\lstset{
  basicstyle=\ttfamily,
  backgroundcolor=\color{codebackground},
  keywordstyle=\color{codekeyword},
  stringstyle=\color{codestring},
  breaklines=true,
  mathescape=true,
  escapeinside={$}{$},
  """ + language_option + r"""
}

\begin{document}
\pagestyle{empty}

\begin{lstlisting}
""" + code_block + r"""
\end{lstlisting}

\end{document}
"""

def render_code_block_with_pdf2image(code_block, output_dir, index):
    """Render a LaTeX code block as an image with better error handling."""
    try:
        import pdf2image
        from PIL import Image
    except ImportError:
        print("Required libraries not installed. Please install them with:")
        print("pip install pdf2image pillow")
        return None
    
    # Create the output directory if it doesn't exist
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Create a temporary directory for LaTeX compilation
    with tempfile.TemporaryDirectory() as temp_dir:
        # Check if there's a language specification at the beginning of the code block
        lang_match = re.match(r'\[language=([a-zA-Z]+)\]', code_block['content'])
        if lang_match:
            language = lang_match.group(1)
            # Remove the language tag from the content
            code_block_content = re.sub(r'^\[language=[a-zA-Z]+\]\s*', '', code_block['content'])
        else:
            language = "python"  # Default
            code_block_content = code_block['content']
        
        # Create a simpler LaTeX document that's more likely to compile successfully
        latex_doc = create_simplified_tex_for_code_block(code_block_content, language)
        
        # Write to a temporary file
        tex_file_path = os.path.join(temp_dir, f"code_block_{index}.tex")
        with open(tex_file_path, "w") as f:
            f.write(latex_doc)
        
        # Also save the LaTeX source for debugging
        debug_tex_path = os.path.join(output_dir, f"debug_code_block_{index}.tex")
        with open(debug_tex_path, "w") as f:
            f.write(latex_doc)
            
        try:
            # Compile to PDF using pdflatex with more detailed error capture
            process = subprocess.run(
                ["pdflatex", "-interaction=nonstopmode", "-output-directory", temp_dir, tex_file_path],
                check=False,
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Save the full LaTeX output to a log file for debugging
            log_path = os.path.join(output_dir, f"latex_log_{index}.txt")
            with open(log_path, "w") as f:
                f.write("STDOUT:\n")
                f.write(process.stdout)
                f.write("\nSTDERR:\n")
                f.write(process.stderr)
            
            # Check if PDF was created
            pdf_path = os.path.join(temp_dir, f"code_block_{index}.pdf")
            if not os.path.exists(pdf_path):
                print(f"LaTeX compilation failed for code block {index}.")
                print(f"Check {log_path} for detailed error information.")
                
                # Print the first few lines of the code block for debugging
                print(f"Code block starts with: {code_block_content[:100]}")
                return None
            
            # Generate unique filename for image
            unique_id = str(uuid.uuid4())[:8]
            img_filename = f"code_block_{index}_{unique_id}.png"
            img_path = os.path.join(output_dir, img_filename)
            
            # Try to copy the PDF for reference
            pdf_output = os.path.join(output_dir, f"code_block_{index}.pdf")
            shutil.copy(pdf_path, pdf_output)
            
            # Convert PDF to PNG using pdf2image with higher DPI for better quality
            try:
                images = pdf2image.convert_from_path(
                    pdf_path, 
                    dpi=300,  # Higher DPI for better quality
                    fmt='png'
                )
                
                # Save the first page
                if images and len(images) > 0:
                    img = images[0]
                    img.save(img_path, 'PNG')
                    
                    # Return image info
                    return {
                        'original': code_block['original'],
                        'img_path': img_filename,
                        'start': code_block['start'],
                        'end': code_block['end']
                    }
                else:
                    print(f"No images generated from PDF for code block {index}.")
                    return None
            except Exception as pdf_img_error:
                print(f"Error converting PDF to image: {pdf_img_error}")
                return None
            
        except Exception as e:
            print(f"Error rendering code block {index}: {e}")
            print(traceback.format_exc())  # Print full traceback for debugging
            return None

def crop_to_content(img):
    """Crop the image to just the code block content using color detection."""
    # Convert to RGB for easier processing
    img_rgb = img.convert('RGB')
    width, height = img.size
    
    # Define a wider range of background colors to detect
    # This includes light gray variations that might be used in code blocks
    background_colors = [
        (248, 248, 248),  # Light gray (original)
        (245, 245, 245),  # Slightly darker gray
        (240, 240, 240),  # Even darker gray
        (250, 250, 250),  # Lighter gray
        (252, 252, 252),  # Very light gray
        (255, 255, 255),  # White (for borders)
    ]
    
    # Initialize bbox coordinates
    min_x, min_y = width, height
    max_x, max_y = 0, 0
    found_background = False
    
    # Use a smaller step size for more accurate detection
    sample_step = 5  # Check every 5th pixel for better coverage
    
    # Define the threshold for color matching
    threshold = 15
    
    # First pass: scan for gray background pixels
    for y in range(0, height, sample_step):
        for x in range(0, width, sample_step):
            pixel = img_rgb.getpixel((x, y))
            
            # Check if pixel is close to any of our background colors
            is_background = False
            for bg_color in background_colors:
                if (abs(pixel[0] - bg_color[0]) < threshold and
                    abs(pixel[1] - bg_color[1]) < threshold and
                    abs(pixel[2] - bg_color[2]) < threshold):
                    is_background = True
                    found_background = True
                    break
            
            # If it's a background pixel, update our bounding box
            if is_background:
                min_x = min(min_x, x)
                min_y = min(min_y, y)
                max_x = max(max_x, x)
                max_y = max(max_y, y)
    
    # If we didn't find any background pixels matching our criteria,
    # or the bounding box is too small, return None to try an alternative method
    if not found_background or max_x - min_x < 100 or max_y - min_y < 100:
        return None
    
    # Second pass: refine the bounding box by scanning the border regions more carefully
    border_scan_width = 50  # Check 50px around the initial bounding box
    
    # Add some padding to ensure we don't cut off any content
    padding = 10
    crop_box = (
        max(0, min_x - padding),
        max(0, min_y - padding),
        min(width, max_x + padding),
        min(height, max_y + padding)
    )
    
    # Crop the image
    cropped = img.crop(crop_box)
    return cropped

def format_latex_code_blocks(content):
    """Format code blocks with LaTeX expressions in a special way without rendering images."""
    code_blocks = extract_code_blocks_with_latex(content)
    
    if not code_blocks:
        return content
    
    # Replace code blocks in reverse order
    code_blocks.sort(key=lambda x: x['start'], reverse=True)
    
    for block in code_blocks:
        # Format with special styling
        formatted_html = f"""<div className="code-block-with-latex">
<pre><code className="language-python">
{block['content']}
</code></pre>
</div>"""
        
        content = content[:block['start']] + formatted_html + content[block['end']:]
    
    return content

def extract_code_blocks_with_latex(content):
    """Extract code blocks that contain LaTeX expressions."""
    code_blocks = []
    # Pattern to match lstlisting environments
    pattern = r'\\begin{lstlisting}(.*?)\\end{lstlisting}'
    
    # Use re.DOTALL to make '.' match newlines
    for match in re.finditer(pattern, content, re.DOTALL):
        code_block = match.group(1).strip()
        # Check if the code block contains any LaTeX symbols or expressions
        if re.search(r'(\$|\\\w+|\$\$|\\mathbb|\\\(|\\\)|\\alpha|\\nabla|\\epsilon)', code_block):
            code_blocks.append({
                'original': match.group(0),
                'content': code_block,
                'start': match.start(),
                'end': match.end()
            })
    
    return code_blocks

def create_tex_for_code_block(code_block, language=None):
    """Create a LaTeX document for a code block with a more distinctive background."""
    # Set language option
    language_option = ""
    if language:
        language_option = f"language={language}"
    
    # Create document with article class
    tex_doc = r"""\documentclass{article}
\usepackage[margin=0.5in]{geometry}
\usepackage{listings}
\usepackage{xcolor}
\usepackage{amsmath}
\usepackage{amssymb}
\usepackage{mathtools}
\usepackage{bm}

% Define a more distinctive background color for easier detection when cropping
\definecolor{codebackground}{RGB}{245, 245, 245}
\definecolor{codeborder}{RGB}{200, 200, 200}
\definecolor{codestring}{RGB}{221, 17, 68}
\definecolor{codekeyword}{RGB}{0, 128, 86}
\definecolor{codecomment}{RGB}{128, 128, 128}

\pagestyle{empty}
"""

    # lstset options with a distinctive frame
    lstset_str = r"""
\lstset{
    basicstyle=\ttfamily\small,
    backgroundcolor=\color{codebackground},
    frame=single,
    framesep=5pt,
    framextopmargin=6pt,
    framexbottommargin=6pt,
    framexleftmargin=6pt,
    framexrightmargin=6pt,
    rulecolor=\color{codeborder},
    commentstyle=\color{codecomment},
    keywordstyle=\color{codekeyword}\bfseries,
    stringstyle=\color{codestring},
    numberstyle=\tiny\color{codecomment},
    breaklines=true,
    breakatwhitespace=false,
    breakindent=0pt,
    tabsize=2,
    columns=flexible,
    showstringspaces=false,
    mathescape=true,
    escapechar=$,
    escapeinside={$}{$}"""

    # Add language if specified
    if language_option:
        lstset_str += f",\n    {language_option}"
    
    # Close lstset
    lstset_str += "\n}"
    
    # Prepare the code block
    code_block = code_block.replace("\\", "\\\\")  # Escape backslashes
    code_block = code_block.replace("$\\\\mathbb", "$\\mathbb")  # Fix double backslash in mathbb
    code_block = code_block.replace("$\\\\nabla", "$\\nabla")  # Fix double backslash in nabla
    code_block = code_block.replace("$\\\\alpha", "$\\alpha")  # Fix double backslash in alpha
    code_block = code_block.replace("$\\\\epsilon", "$\\epsilon")  # Fix double backslash in epsilon
    
    # Add explicit page size
    geometry_str = r"""
\geometry{
  paperwidth=8.5in,
  paperheight=11in,
  margin=0.5in
}
"""

    # Complete document with our frame around code
    document_part = r"""
\begin{document}

% Create a more distinctive box around the code
\fboxsep=10pt
\fboxrule=1pt
\begin{center}
\begin{lstlisting}
"""

    ending_part = r"""
\end{lstlisting}
\end{center}
\end{document}
"""
    
    return tex_doc + geometry_str + lstset_str + document_part + code_block + ending_part

def render_code_block_as_pdf(code_block, output_dir, index):
    """Render a LaTeX code block as a PDF."""
    # Create the output directory if it doesn't exist
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Create a temporary directory for LaTeX compilation
    with tempfile.TemporaryDirectory() as temp_dir:
        # Check if there's a language specification at the beginning of the code block
        lang_match = re.match(r'\[language=([a-zA-Z]+)\]', code_block['content'])
        if lang_match:
            language = lang_match.group(1)
            # Remove the language tag from the content
            code_block_content = re.sub(r'^\[language=[a-zA-Z]+\]\s*', '', code_block['content'])
        else:
            language = "python"  # Default
            code_block_content = code_block['content']
        
        # Create the standalone LaTeX document
        latex_doc = create_tex_for_code_block(code_block_content, language)
        
        # Write to a temporary file
        tex_file_path = os.path.join(temp_dir, f"code_block_{index}.tex")
        with open(tex_file_path, "w") as f:
            f.write(latex_doc)
        
        # Also save the LaTeX source for debugging
        debug_tex_path = os.path.join(output_dir, f"debug_code_block_{index}.tex")
        with open(debug_tex_path, "w") as f:
            f.write(latex_doc)
            
        try:
            # Compile to PDF using pdflatex
            process = subprocess.run(
                ["pdflatex", "-interaction=nonstopmode", "-output-directory", temp_dir, tex_file_path],
                check=False,
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Check if PDF was created
            pdf_temp_path = os.path.join(temp_dir, f"code_block_{index}.pdf")
            if not os.path.exists(pdf_temp_path):
                print(f"LaTeX compilation failed for code block {index}.")
                return None
            
            # Generate unique filename for PDF
            unique_id = str(uuid.uuid4())[:8]
            pdf_filename = f"code_block_{index}_{unique_id}.pdf"
            pdf_path = os.path.join(output_dir, pdf_filename)
            
            # Copy the PDF to output directory
            shutil.copy(pdf_temp_path, pdf_path)
            
            # Return PDF info
            return {
                'original': code_block['original'],
                'pdf_path': pdf_filename,
                'start': code_block['start'],
                'end': code_block['end']
            }
            
        except Exception as e:
            print(f"Error rendering code block {index}: {e}")
            return None

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
    """Convert LaTeX math delimiters to KaTeX compatible format."""
    # Convert inline math
    content = re.sub(r'\\\((.*?)\\\)', r'$\1$', content)
    
    # Convert display math
    content = re.sub(r'\\\[([\s\S]*?)\\\]', r'$$\1$$', content)
    
    # Also handle equation environments that pandoc might preserve
    content = re.sub(r'\\begin\{equation\}([\s\S]*?)\\end\{equation\}', r'$$\1$$', content)
    
    # Handle align and align* environments
    content = re.sub(r'\\begin\{align\*?\}([\s\S]*?)\\end\{align\*?\}', r'$$\1$$', content)

    content = re.sub(r'\\begin\{aligned\}([\s\S]*?)\\end\{aligned\}', 
                     lambda m: r'\begin{aligned}' + m.group(1).replace(r'\\', r'\\\\') + r'\end{aligned}', 
                     content)
    
    return content

def handle_marginfigure(content, tex_file_path, output_dir):
    """Handle marginfigure LaTeX environments and convert to clean image references."""
    # Get the chapter name for image paths
    chapter_name = os.path.splitext(os.path.basename(tex_file_path))[0]
    
    def process_marginfigure(match):
        """Process a marginfigure environment and extract just the image."""
        figure_content = match.group(1)
        
        # Extract the image from includegraphics
        img_match = re.search(r'\\includegraphics(?:\[([^\]]*)\])?\{([^}]*)\}', figure_content)
        if img_match:
            # Get the image path and clean it
            image_path = img_match.group(2)
            image_basename = os.path.basename(image_path)
            
            # Extract caption if needed (optional)
            caption_match = re.search(r'\\caption\{([^}]*)\}', figure_content)
            caption = caption_match.group(1) if caption_match else "image"
            
            # Create a clean image reference - either with the full path if provided
            # or with the proper chapter-based path structure
            if "/" in image_path:
                # If it's a path like figures/part1b/multidimensional_optimization/contour0.png
                # We'll keep just the filename and use the proper chapter path
                image_filename = os.path.basename(image_path)
                return f'![{caption}]({BASE_PATH}/figures/{chapter_name}/{image_filename})'
            else:
                # If it's a simple filename, use the chapter path
                return f'![{caption}]({BASE_PATH}/figures/{chapter_name}/{image_basename})'
        
        # If no image found, return an empty string or placeholder
        return ""
    
    # Process all marginfigure environments
    content = re.sub(r'\\begin\{marginfigure\}(.*?)\\end\{marginfigure\}', 
                     process_marginfigure, 
                     content, 
                     flags=re.DOTALL)
    
    # Also handle the converted ::: marginfigure pattern that might appear after pandoc conversion
    content = re.sub(r'::: marginfigure(.*?):::', 
                     lambda m: re.search(r'!\[.*?\]\(.*?\)', m.group(1)).group(0) if re.search(r'!\[.*?\]\(.*?\)', m.group(1)) else "", 
                     content, 
                     flags=re.DOTALL)
    
    # Clean up any remaining artifacts
    content = re.sub(r'(!\[.*?\]\(.*?\))None\{width="[^"]*"\}', r'\1', content)
    
    return content

def fix_missing_backslashes(content):
    """Fix missing backslashes in LaTeX environments like 'begin{aligned}'."""
    # Fix 'begin' without backslash
    content = re.sub(r'(\$\$\s*)begin(\{[a-zA-Z*]+\})', r'\1\\begin\2', content)
    
    # Fix 'end' without backslash
    content = re.sub(r'(\s*)end(\{[a-zA-Z*]+\}\s*\$\$)', r'\1\\end\2', content)
    
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

def handle_equation_labels_and_references(content):
    """
    Process equation labels and references to support proper cross-referencing in MDX.
    This converts LaTeX \label and \ref to a format compatible with MDX rendering.
    """
    # First, create a dictionary to store all equation labels and their corresponding numbers
    equation_labels = {}
    equation_count = 0
    
    # Find all labeled equations and assign numbers
    def process_equation_label(match):
        nonlocal equation_count
        equation_count += 1
        
        full_match = match.group(0)
        equation_content = match.group(1)
        label_match = re.search(r'\\label\{([^}]+)\}', equation_content)
        
        if label_match:
            label = label_match.group(1)
            equation_labels[label] = equation_count
            
            # Replace the label with an HTML anchor and keep the number
            equation_with_anchor = re.sub(
                r'\\label\{([^}]+)\}',
                f'{{/* equation-{equation_count} */}}',
                equation_content
            )
            
            # Add the equation number in a visually appealing way
            return f"""\\begin{{equation}}
{equation_with_anchor}
\\tag{{{equation_count}}}
\\end{{equation}}"""
        
        return full_match
    
    # Process all equation environments
    content = re.sub(
        r'\\begin\{equation\}(.*?)\\end\{equation\}',
        process_equation_label,
        content,
        flags=re.DOTALL
    )
    
    # After equations are processed and numbered, replace all references
    def replace_references(match):
        ref_label = match.group(1)
        if ref_label in equation_labels:
            equation_number = equation_labels[ref_label]
            return f"Equation {equation_number}"
        return f"Equation {ref_label}"  # Fallback if label not found
    
    # Replace \ref{label} with "Equation X"
    content = re.sub(r'\\ref\{([^}]+)\}', replace_references, content)
    
    # Also handle any variants like Equation~\ref or Equation~\\ref
    content = re.sub(r'Equation\s*~?\s*\\ref\{([^}]+)\}', replace_references, content)
    
    return content

def process_for_mdx_equation_references(mdx_content, equation_labels):
    """
    Process the converted MDX content to add equation numbers and fix references.
    This is applied after the pandoc conversion.
    """
    # Find equations that have our special comment markers
    def add_equation_number(match):
        equation_content = match.group(1)
        
        # Extract the equation number from the comment
        number_match = re.search(r'\{\s*\/\*\s*equation-(\d+)\s*\*\/\s*\}', equation_content)
        if number_match:
            equation_number = number_match.group(1)
            
            # Remove the comment marker
            clean_content = re.sub(r'\{\s*\/\*\s*equation-\d+\s*\*\/\s*\}', '', equation_content)
            
            # Add the equation number using MDX-compatible syntax
            return f"""$$
{clean_content} \\tag{{{equation_number}}}
$$"""
        
        return match.group(0)
    
    # Process equations with numbers
    mdx_content = re.sub(
        r'\$\$(.*?)\$\$',
        add_equation_number,
        mdx_content,
        flags=re.DOTALL
    )
    
    # Fix any remaining text references that weren't caught earlier
    for label, number in equation_labels.items():
        mdx_content = re.sub(
            rf'Equation\\?~?\\?\s*{label}', 
            f"Equation {number}", 
            mdx_content
        )
    
    return mdx_content

def remove_labels(content):
    """Remove LaTeX label tags and references."""
    content = re.sub(r'\\label\{[^}]*\}', '', content)
    content = re.sub(r'\{#[^}]*\}', '', content)
    content = re.sub(r'\{reference-type="[^"]*"\s+reference="[^"]*"\}', '', content)
    content = re.sub(r'\[\[.*?\]\]\(#.*?\)', '', content)
    content = re.sub(r'(^#\s+[^\\]+)\\', r'\1', content, flags=re.MULTILINE)
    content = re.sub(r'\[\]\s*\n', '\n', content)
    content = re.sub(r'Table \[\[.*?\]\]', 'Table', content)
    content = re.sub(r'\(#.*?\)', '', content)
    content = re.sub(r'\[\[.*?\]\]', '', content)
    content = re.sub(r'\n\s*\n\s*\n', '\n\n', content)
    return content

def remove_labels_preserve_equations(content):
    """Remove LaTeX label tags and references while preserving equation labels."""
    # Remove most labels but preserve equation labels
    content = re.sub(r'\\label\{(?!eq)[^}]*\}', '', content)  # Remove non-equation labels
    content = re.sub(r'\{#[^}]*\}', '', content)
    content = re.sub(r'\{reference-type="[^"]*"\s+reference="[^"]*"\}', '', content)
    content = re.sub(r'\[\[.*?\]\]\(#.*?\)', '', content)
    content = re.sub(r'(^#\s+[^\\]+)\\', r'\1', content, flags=re.MULTILINE)
    content = re.sub(r'\[\]\s*\n', '\n', content)
    content = re.sub(r'Table \[\[.*?\]\]', 'Table', content)
    content = re.sub(r'\(#.*?\)', '', content)
    content = re.sub(r'\[\[.*?\]\]', '', content)
    content = re.sub(r'\n\s*\n\s*\n', '\n\n', content)
    return content

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
                img_tag = f'<img src="{BASE_PATH}/figures/{chapter_name}/{output_filename}" alt="TikZ diagram" />'
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
        relative_path = f'{BASE_PATH}/figures/{chapter_name}/{os.path.basename(image_basename)}.png'
        
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
                public_path = f'{BASE_PATH}/figures/{chapter_name}/{os.path.basename(image_basename)}.png'
                
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
    # Fix any image src that might not have the correct basePath in HTML tags
    content = re.sub(r'<img src="(?!/|http|' + re.escape(BASE_PATH) + ')([^"]+)"', 
                    r'<img src="' + BASE_PATH + r'/\1"', content)
    
    # Fix any image src that starts with a slash but doesn't have basePath
    if BASE_PATH:
        content = re.sub(r'<img src="(/[^"' + re.escape(BASE_PATH) + r'][^"]*)"', 
                        r'<img src="' + BASE_PATH + r'\1"', content)
    
    # Fix any image paths in Markdown format ![alt](path) 
    content = re.sub(r'!\[(.*?)\]\((?!/|http|' + re.escape(BASE_PATH) + ')([^)]+)\)', 
                    r'![\1](' + BASE_PATH + r'/\2)', content)
    
    # Also handle Markdown format with attributes ![alt](path){width="x"} 
    content = re.sub(r'!\[(.*?)\]\((?!/|http|' + re.escape(BASE_PATH) + ')([^)]+)\)(\{[^}]*\})', 
                    r'![\1](' + BASE_PATH + r'/\2)\3', content)
    
    # Check and fix any malformed paths (double slashes, etc.)
    content = re.sub(r'src="//+', r'src="/', content)
    content = re.sub(r'\]\(//+', r'](/', content)
    
    # Ensure that basePath is properly added without duplication
    if BASE_PATH:
        content = re.sub(r'src="' + re.escape(BASE_PATH) + re.escape(BASE_PATH), 
                        r'src="' + BASE_PATH, content)
        content = re.sub(r'\]\(' + re.escape(BASE_PATH) + re.escape(BASE_PATH), 
                        r'](' + BASE_PATH, content)
    
    return content

# def ensure_image_paths(content):
#     """Ensure all image paths in the MDX content have the correct format while preserving code block images."""
#     # First, find and temporarily mark code block image references to protect them
#     protected_content = re.sub(
#         r'(!\[image\])(\(/code-blocks/[^)]+\))',
#         r'CODE_BLOCK_IMAGE_MARKER\2CODE_BLOCK_IMAGE_END',
#         content
#     )
    
#     # Now apply normal path fixing to non-code-block images
#     # Fix any image src that might not have a leading slash in HTML tags
#     protected_content = re.sub(r'<img src="(?!\/|http)([^"]+)"', r'<img src="/\1"', protected_content)
    
#     # Fix any image paths in Markdown format ![alt](path) that are NOT code block images
#     protected_content = re.sub(
#         r'(?<!CODE_BLOCK_IMAGE_MARKER)!\[(.*?)\]\((?!\/|http)([^)]+)\)',
#         r'![\1](/\2)',
#         protected_content
#     )
    
#     # Also handle Markdown format with attributes ![alt](path){width="x"} 
#     protected_content = re.sub(
#         r'(?<!CODE_BLOCK_IMAGE_MARKER)!\[(.*?)\]\((?!\/|http)([^)]+)\)(\{[^}]*\})',
#         r'![\1](/\2)\3',
#         protected_content
#     )
    
#     # Convert any Markdown images to the chapter-specific path format
#     chapter_name = os.environ.get('CURRENT_CHAPTER_NAME', '')
#     if chapter_name:
#         # Handle paths that aren't already in the /figures/chapter structure
#         def fix_paths(match):
#             # Skip if this is a code block image path
#             if "CODE_BLOCK_IMAGE_MARKER" in match.string[max(0, match.start()-30):match.start()]:
#                 return match.group(0)
                
#             alt_text = match.group(1)
#             path = match.group(2)
#             attrs = match.group(3) if len(match.groups()) > 2 else ''
            
#             # Skip if already in correct format or if it's a code-blocks path
#             if re.match(r'^/figures/[^/]+/', path) or re.match(r'^/code-blocks/[^/]+/', path):
#                 return f'![{alt_text}]({path}){attrs}'
            
#             # Extract filename from path
#             filename = os.path.basename(path)
#             # Create new path in chapter figures directory
#             new_path = f'/figures/{chapter_name}/{filename}'
#             return f'![{alt_text}]({new_path}){attrs}'
        
#         # Apply the path fixing to Markdown images, but not to code block images
#         protected_content = re.sub(
#             r'(?<!CODE_BLOCK_IMAGE_MARKER)!\[(.*?)\]\(([^)]+)\)(\{[^}]*\})?',
#             fix_paths,
#             protected_content
#         )
        
#         # Handle the specific pattern with figures/part1b/... paths
#         protected_content = re.sub(
#             r'(?<!CODE_BLOCK_IMAGE_MARKER)!\[(.*?)\]\(figures/part1b/[^)]+/([^/)]+)\)(\{[^}]*\})?', 
#             lambda m: f'![{m.group(1)}](/figures/{chapter_name}/{m.group(2)}){m.group(3) if m.group(3) else ""}', 
#             protected_content
#         )
    
#     # Check and fix any malformed paths (double slashes, etc.)
#     protected_content = re.sub(r'src="//+', r'src="/', protected_content)
#     protected_content = re.sub(r'\]\(//+', r'](/', protected_content)
    
#     # Now restore the code block image references
#     final_content = protected_content.replace('CODE_BLOCK_IMAGE_MARKER', '![image').replace('CODE_BLOCK_IMAGE_END', '')
    
#     return final_content

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

def clean_prerequisites_and_difficulty(mdx_content):
    """
    Clean up prerequisites and difficulty level sections in converted MDX content.
    Handles both chapters with and without difficulty levels.
    
    Args:
        mdx_content (str): The MDX content to clean
        
    Returns:
        str: Cleaned MDX content
    """
    # First, remove prerequisites section completely for chapters with difficulty level
    mdx_content = re.sub(
        r'(-{70,})([\s\S]*?)(\*\*Difficulty Level:\*\*[\s\S]*?)(-{70,})',
        r'\1\n\n\3\n\n\4',  # Keep only the parts we want with proper spacing
        mdx_content
    )
    
    # Then handle chapters with ONLY Prerequisites (no Difficulty Level)
    mdx_content = re.sub(
        r'(-{70,})([\s\S]*?\*\*Prerequisites:\*\*[\s\S]*?)(-{70,})',
        r'\1\n\n\3',  # Remove Prerequisites completely
        mdx_content
    )
    
    # Clean up backslashes before asterisks
    mdx_content = re.sub(
        r'(\*\*Difficulty Level:\*\*)\s*\\(\*+)(?:\\)*',
        r'\1 \2',  # Clean format
        mdx_content
    )
    
    # Clean up backslashes after asterisks
    mdx_content = re.sub(
        r'(\*\*Difficulty Level:\*\*)\s*(\*+)\\',
        r'\1 \2',  # Clean format
        mdx_content
    )
    
    # Final cleanup for any remaining backslashes
    mdx_content = re.sub(
        r'(\*\*Difficulty Level:\*\*\s*\*+)\\+',
        r'\1',  # Remove any remaining backslashes
        mdx_content
    )
    
    return mdx_content

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

        content = handle_marginfigure(content, tex_file, output_dir)
        
        # Process subfigures first, they're more complex
        content = handle_subfigures(content, tex_file, output_dir)
        
        # Process TikZ diagrams before conversion
        content = extract_and_render_tikz(content, tex_file, output_dir)
        
        # Extract code blocks and render them, but don't replace yet
        code_blocks = extract_code_blocks_with_latex(content)
        img_dir = os.path.join(os.path.abspath(os.path.dirname(os.path.dirname(__file__))), 
                              'public', 'code-blocks', chapter_name)
        
        # Ensure directory exists
        if not os.path.exists(img_dir):
            os.makedirs(img_dir)
            
        # Render each code block
        rendered_blocks = []
        for i, block in enumerate(code_blocks):
            print(f"Rendering code block {i+1}: {block['content'][:50]}...")
            rendered = render_code_block_with_transparency(block, img_dir, i)
            if rendered and 'img_path' in rendered:
                rendered_blocks.append(rendered)
                print(f"Successfully rendered code block {i+1} with transparency")
            else:
                print(f"Using fallback for code block {i+1}")
                # Use fallback
                fallback_html = f"""<div className="code-block-with-latex">
<pre><code className="language-python">
{block['content']}
</code></pre>
</div>"""
                rendered_blocks.append({
                    'original': block['original'],
                    'fallback_html': fallback_html,
                    'start': block['start'],
                    'end': block['end']
                })
        
        # Replace code blocks with placeholders to preserve them during conversion
        for i, block in enumerate(code_blocks):
            unique_placeholder = f"CODE_BLOCK_PLACEHOLDER_{i}_{uuid.uuid4().hex[:8]}"
            content = content.replace(block['original'], unique_placeholder)
            block['placeholder'] = unique_placeholder
        
        # Convert to markdown
        md_content = pypandoc.convert_text(content, 'markdown', format='latex')

        # Apply regular markdown processing
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
        
        # Now replace the placeholders with actual image tags
        for i, block in enumerate(code_blocks):
            if i < len(rendered_blocks):
                rendered = rendered_blocks[i]
                if 'img_path' in rendered:
                    # Create clean image tag
                    img_tag = f'![image]({BASE_PATH}/code-blocks/{chapter_name}/{rendered["img_path"]})'
                    mdx_content = mdx_content.replace(block['placeholder'], img_tag)
                elif 'fallback_html' in rendered:
                    mdx_content = mdx_content.replace(block['placeholder'], rendered['fallback_html'])
        
        # Final cleanup to remove any remaining backslashes or "None" artifacts
        mdx_content = mdx_content.replace('\\![', '![')
        mdx_content = mdx_content.replace('\\]', ']')
        mdx_content = mdx_content.replace('\\(', '(')
        mdx_content = mdx_content.replace('\\)', ')')
        mdx_content = re.sub(r'(!\[image\]\(' + re.escape(BASE_PATH) + r'/code-blocks/[^)]+\))None', r'\1', mdx_content)

        def fix_aligned_line_breaks(match):
            full_match = match.group(0)
            # Replace \\ with \\\\ but only when it's a line break (not part of another command)
            return full_match.replace(' \\\\', ' \\\\\\\\')

        # Apply this fix to all math environments containing aligned environments
        mdx_content = re.sub(r'\$\$\\begin\\{aligned\\}[\s\S]*?\\end\\{aligned\\}\$\$', 
                         fix_aligned_line_breaks, mdx_content)
        
        mdx_content = clean_prerequisites_and_difficulty(mdx_content)

        # Add CSS for code block images
        css_for_code_blocks = """
<style jsx global>{`
  .code-block-container {
    display: block;
    margin: 1.5rem 0;
    padding: 0;
  }
  .code-block-image {
    display: block;
    width: auto;
    max-width: 100%;
    height: auto;
    filter: drop-shadow(0 0 0 transparent); /* Force transparency rendering in some browsers */
  }
  /* Other styles... */
`}</style>
""" 

        mdx_content = css_for_code_blocks + mdx_content
        
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