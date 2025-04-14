import os
import sys
import pypandoc
import re

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

def convert_tex_to_mdx(tex_file, output_dir):
    """Convert LaTeX file to MDX format."""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    try:
        with open(tex_file, 'r') as file:
            content = file.read()

        title = extract_title(content)

        md_content = pypandoc.convert_text(content, 'markdown', format='latex')

        mdx_content = escape_braces(md_content)
        mdx_content = remove_language_references(mdx_content)

        mdx_content = clean_code_blocks(mdx_content)
        mdx_content = fix_set_notation(mdx_content)
        mdx_content = fix_math_delimiters(mdx_content)
        mdx_content = format_tables(mdx_content)
        mdx_content = remove_labels(mdx_content)
        mdx_content = add_frontmatter(mdx_content, title)

        mdx_file = os.path.join(output_dir, 'index.mdx')
        with open(mdx_file, 'w') as file:
            file.write(mdx_content)

        print(f"Successfully converted {tex_file} to {mdx_file}")
        print(f"Title: {title}")

    except Exception as e:
        print(f"Error converting {tex_file}: {e}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python covert_tex_to_md.py <input_tex_file> <output_directory>")
        sys.exit(1)

    tex_file = sys.argv[1]
    output_dir = sys.argv[2]
    convert_tex_to_mdx(tex_file, output_dir)