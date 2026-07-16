import json

def main():
    report_path = "AutoPlanAI_Project_Report.md"
    output_html = "project_report_rendered.html"

    with open(report_path, "r", encoding="utf-8", errors="ignore") as f:
        md_content = f.read()

    # Escape the markdown content for embedding as a JSON string in JS
    escaped_md = json.dumps(md_content)

    # HTML template with marked.js and mermaid.js to compile markdown to HTML live in the browser.
    # Uses Outfit and Plus Jakarta Sans, dark-theme layout matching the main app design.
    html_template = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AutoPlan AI - Project Report & Architecture Specifications</title>
    
    <!-- Google Fonts -->
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&family=Plus+Jakarta+Sans:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    
    <!-- Marked.js (Markdown Parser) -->
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    
    <!-- Mermaid.js (Diagram Parser) -->
    <script type="module">
        import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
        mermaid.initialize({
            startOnLoad: false,
            theme: 'dark',
            securityLevel: 'loose',
            flowchart: { useMaxWidth: false, htmlLabels: true }
        });
        window.mermaid = mermaid;
    </script>

    <style>
        :root {
            /* Dark Theme (Default) */
            --bg-primary: #0B0F19;
            --bg-secondary: #151D30;
            --accent-primary: #38BDF8;   /* Sky Blue */
            --accent-secondary: #6366F1; /* Indigo */
            --accent-success: #10B981;   /* Emerald */
            --accent-error: #EF4444;     /* Red */
            --text-main: #E2E8F0;
            --text-muted: #94A3B8;
            --border-color: rgba(255, 255, 255, 0.08);
            --code-bg: #0F172A;
            --code-text: #F87171;
            --heading-color: #FFFFFF;
            --blockquote-bg: rgba(56, 189, 248, 0.05);
            --tr-hover: rgba(255, 255, 255, 0.01);
        }

        body.theme-light {
            /* Professional Light Theme */
            --bg-primary: #F8FAFC;       /* Slate 50 */
            --bg-secondary: #FFFFFF;     /* White */
            --accent-primary: #0284C7;   /* Sky 600 */
            --accent-secondary: #4F46E5; /* Indigo 600 */
            --accent-success: #059669;   /* Emerald 600 */
            --accent-error: #DC2626;     /* Red 600 */
            --text-main: #334155;        /* Slate 700 */
            --text-muted: #64748B;       /* Slate 500 */
            --border-color: rgba(0, 0, 0, 0.08);
            --code-bg: #F1F5F9;          /* Slate 100 */
            --code-text: #DC2626;        /* Red 600 */
            --heading-color: #0F172A;    /* Slate 900 */
            --blockquote-bg: rgba(2, 132, 199, 0.05);
            --tr-hover: rgba(0, 0, 0, 0.01);
        }

        body {
            font-family: 'Plus Jakarta Sans', sans-serif;
            background-color: var(--bg-primary);
            color: var(--text-main);
            margin: 0;
            padding: 0;
            display: flex;
            height: 100vh;
            overflow: hidden;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }

        /* Sidebar navigation */
        .sidebar {
            width: 320px;
            background-color: var(--bg-secondary);
            border-right: 1px solid var(--border-color);
            display: flex;
            flex-direction: column;
            overflow-y: auto;
            z-index: 10;
            transition: margin-left 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }

        body.sidebar-collapsed .sidebar {
            margin-left: -320px;
        }

        .sidebar-header {
            padding: 24px;
            border-bottom: 1px solid var(--border-color);
        }

        .sidebar-header h2 {
            margin: 0;
            font-family: 'Outfit', sans-serif;
            font-size: 1.3rem;
            background: linear-gradient(135deg, var(--accent-primary) 0%, var(--accent-secondary) 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .sidebar-header p {
            margin: 8px 0 0 0;
            font-size: 0.8rem;
            color: var(--text-muted);
        }

        .toc-list {
            list-style: none;
            padding: 20px;
            margin: 0;
            display: flex;
            flex-direction: column;
            gap: 8px;
        }

        .toc-item a {
            color: var(--text-muted);
            text-decoration: none;
            font-size: 0.85rem;
            display: block;
            padding: 8px 12px;
            border-radius: 6px;
            transition: all 0.2s ease;
            border-left: 2px solid transparent;
        }

        .toc-item a:hover {
            background-color: rgba(255, 255, 255, 0.02);
            color: var(--text-main);
        }

        .toc-item.level-2 {
            font-weight: 600;
        }

        .toc-item.level-3 {
            padding-left: 15px;
            font-size: 0.8rem;
        }

        .toc-item.active a {
            background: linear-gradient(90deg, rgba(56, 189, 248, 0.1) 0%, rgba(99, 102, 241, 0.05) 100%);
            color: var(--accent-primary);
            border-left-color: var(--accent-primary);
        }

        /* Document view pane */
        .content-pane {
            flex: 1;
            overflow-y: auto;
            scroll-behavior: smooth;
            padding: 40px 80px 80px 80px;
            position: relative;
        }

        .content-container {
            max-width: 900px;
            margin: 0 auto;
        }

        /* Floating Sidebar Toggle Button */
        .sidebar-toggle {
            position: fixed;
            top: 15px;
            left: 15px;
            background-color: var(--bg-secondary);
            border: 1px solid var(--border-color);
            color: var(--text-main);
            width: 40px;
            height: 40px;
            border-radius: 8px;
            cursor: pointer;
            z-index: 100;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.2s ease;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2);
        }

        .sidebar-toggle:hover {
            background-color: var(--accent-secondary);
            color: #FFFFFF;
            border-color: transparent;
        }

        /* Floating Theme Toggle Button */
        .theme-toggle {
            position: fixed;
            top: 15px;
            right: 15px;
            background-color: var(--bg-secondary);
            border: 1px solid var(--border-color);
            color: var(--text-main);
            width: 40px;
            height: 40px;
            border-radius: 8px;
            cursor: pointer;
            z-index: 100;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.2s ease;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2);
        }

        .theme-toggle:hover {
            background-color: var(--accent-secondary);
            color: #FFFFFF;
            border-color: transparent;
        }

        /* Typography & Custom markdown styling */
        h1, h2, h3, h4 {
            font-family: 'Outfit', sans-serif;
            font-weight: 700;
            color: var(--heading-color);
            margin-top: 1.8em;
            margin-bottom: 0.6em;
            scroll-margin-top: 80px; /* Offset for scroll to header */
        }

        h1 {
            font-size: 2.4rem;
            border-bottom: 2px solid var(--border-color);
            padding-bottom: 12px;
            background: linear-gradient(135deg, var(--accent-primary) 0%, var(--accent-secondary) 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-top: 0;
        }

        h2 {
            font-size: 1.7rem;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 8px;
            color: var(--accent-primary);
        }

        h3 {
            font-size: 1.25rem;
            color: var(--text-main);
        }

        p {
            line-height: 1.7;
            font-size: 0.95rem;
            margin-bottom: 1.5em;
            color: var(--text-main);
        }

        ul, ol {
            padding-left: 24px;
            margin-bottom: 1.5em;
            line-height: 1.7;
            font-size: 0.95rem;
            color: var(--text-main);
        }

        li {
            margin-bottom: 0.5em;
        }

        /* Inline code and code blocks */
        code {
            font-family: Consolas, Monaco, 'Andale Mono', 'Ubuntu Mono', monospace;
            background-color: var(--code-bg);
            padding: 3px 6px;
            border-radius: 4px;
            font-size: 0.905rem;
            color: var(--code-text);
        }

        pre code {
            display: block;
            padding: 16px;
            overflow-x: auto;
            background-color: var(--code-bg);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            color: var(--text-muted);
            line-height: 1.5;
        }

        /* Table styling */
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 1.5em;
            margin-bottom: 2em;
            font-size: 0.9rem;
        }

        th {
            background-color: var(--bg-secondary);
            color: var(--accent-primary);
            font-weight: 600;
            text-align: left;
            padding: 12px 16px;
            border-bottom: 2px solid var(--border-color);
        }

        td {
            padding: 12px 16px;
            border-bottom: 1px solid var(--border-color);
            color: var(--text-main);
        }

        tr:hover td {
            background-color: var(--tr-hover);
        }

        /* Mermaid diagram wrapper */
        .mermaid-container {
            background-color: var(--bg-secondary);
            border-radius: 12px;
            padding: 30px;
            margin: 2em 0;
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.3);
            border: 1px solid var(--border-color);
            display: flex;
            justify-content: center;
            align-items: center;
            overflow-x: auto;
        }

        .mermaid {
            width: 100%;
            text-align: center;
        }

        .mermaid svg {
            max-width: 100% !important;
            height: auto !important;
        }

        /* Blockquotes */
        blockquote {
            border-left: 4px solid var(--accent-primary);
            background-color: var(--blockquote-bg);
            padding: 12px 24px;
            margin: 1.5em 0;
            border-radius: 0 8px 8px 0;
        }

        blockquote p {
            margin: 0;
            font-style: italic;
            color: var(--text-main);
        }

        /* Custom GitHub style alerts */
        .markdown-alert {
            padding: 12px 20px;
            margin: 1.5em 0;
            border-left: 4px solid transparent;
            border-radius: 6px;
            background-color: var(--bg-secondary);
        }
        .markdown-alert-note { border-left-color: var(--accent-primary); background-color: var(--blockquote-bg); }
        .markdown-alert-tip { border-left-color: var(--accent-success); background-color: rgba(16, 185, 129, 0.05); }
        .markdown-alert-warning { border-left-color: #FBBF24; background-color: rgba(251, 191, 36, 0.05); }

        /* Scrollbar styles */
        ::-webkit-scrollbar {
            width: 8px;
            height: 8px;
        }

        ::-webkit-scrollbar-track {
            background: var(--bg-primary);
        }

        ::-webkit-scrollbar-thumb {
            background: #1E293B;
            border-radius: 4px;
        }

        ::-webkit-scrollbar-thumb:hover {
            background: #334155;
        }
    </style>
</head>
<body class="theme-dark">
    <!-- Check and load theme before render to avoid flash -->
    <script>
        const savedTheme = localStorage.getItem('theme');
        if (savedTheme === 'light') {
            document.body.classList.remove('theme-dark');
            document.body.classList.add('theme-light');
        }
    </script>

    <button class="sidebar-toggle" onclick="toggleSidebar()" aria-label="Toggle Sidebar">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <line x1="3" y1="12" x2="21" y2="12"></line>
            <line x1="3" y1="6" x2="21" y2="6"></line>
            <line x1="3" y1="18" x2="21" y2="18"></line>
        </svg>
    </button>

    <button class="theme-toggle" onclick="toggleTheme()" aria-label="Toggle Light/Dark Theme">
        <svg id="theme-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>
        </svg>
    </button>

    <div class="sidebar">
        <div class="sidebar-header">
            <h2>🏭 AutoPlan AI</h2>
            <p>System Architecture & Project Specifications</p>
        </div>
        <ul class="toc-list" id="toc"></ul>
    </div>
    <div class="content-pane" id="pane">
        <div class="content-container" id="rendered-content">
            <p style="text-align: center; color: var(--text-muted); margin-top: 100px;">Rendering project report and drawing diagrams, please wait...</p>
        </div>
    </div>

    <script>
        const markdownSource = _MARKDOWN_SOURCE_PLACEHOLDER_;

        function toggleSidebar() {
            document.body.classList.toggle('sidebar-collapsed');
        }

        function toggleTheme() {
            const body = document.body;
            const isDark = body.classList.contains('theme-dark');
            
            if (isDark) {
                body.classList.remove('theme-dark');
                body.classList.add('theme-light');
                localStorage.setItem('theme', 'light');
                document.getElementById('theme-icon').innerHTML = '<circle cx="12" cy="12" r="5"></circle><line x1="12" y1="1" x2="12" y2="3"></line><line x1="12" y1="21" x2="12" y2="23"></line><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line x1="1" y1="12" x2="3" y2="12"></line><line x1="21" y1="12" x2="23" y2="12"></line><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>';
            } else {
                body.classList.remove('theme-light');
                body.classList.add('theme-dark');
                localStorage.setItem('theme', 'dark');
                document.getElementById('theme-icon').innerHTML = '<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>';
            }
            
            // Re-render diagrams to apply light/dark theme styling
            renderMermaidDiagrams();
        }

        // Initialize theme icon on load
        function initThemeIcon() {
            const isLight = document.body.classList.contains('theme-light');
            const icon = document.getElementById('theme-icon');
            if (isLight) {
                icon.innerHTML = '<circle cx="12" cy="12" r="5"></circle><line x1="12" y1="1" x2="12" y2="3"></line><line x1="12" y1="21" x2="12" y2="23"></line><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line x1="1" y1="12" x2="3" y2="12"></line><line x1="21" y1="12" x2="23" y2="12"></line><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>';
            } else {
                icon.innerHTML = '<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>';
            }
        }

        async function renderDocument() {
            const renderedContainer = document.getElementById('rendered-content');
            
            // Parse Markdown to HTML using standard marked parser
            const parsedHtml = marked.parse(markdownSource);
            renderedContainer.innerHTML = parsedHtml;

            // Find all blocks of mermaid code and convert them to div containers
            const codeBlocks = document.querySelectorAll('pre code');
            codeBlocks.forEach(el => {
                const text = el.textContent.trim();
                const isMermaid = el.classList.contains('language-mermaid') || 
                                   el.classList.contains('lang-mermaid') ||
                                   el.classList.contains('mermaid') ||
                                   text.startsWith('flowchart ') || 
                                   text.startsWith('graph ') || 
                                   text.startsWith('sequenceDiagram') || 
                                   text.startsWith('gantt') || 
                                   text.startsWith('classDiagram') || 
                                   text.startsWith('stateDiagram') || 
                                   text.startsWith('pie') || 
                                   text.startsWith('journey');
                
                if (isMermaid) {
                    const pre = el.parentElement;
                    const containerDiv = document.createElement('div');
                    containerDiv.className = 'mermaid-container';
                    const mermaidDiv = document.createElement('div');
                    mermaidDiv.className = 'mermaid';
                    mermaidDiv.textContent = text;
                    containerDiv.appendChild(mermaidDiv);
                    pre.replaceWith(containerDiv);
                }
            });

            // Initialize Table of Contents
            buildTOC();

            // Set up correct icon
            initThemeIcon();

            // Render Mermaid diagrams
            await renderMermaidDiagrams();
        }

        async function renderMermaidDiagrams() {
            const isLight = document.body.classList.contains('theme-light');
            const theme = isLight ? 'default' : 'dark';
            
            if (window.mermaid) {
                window.mermaid.initialize({
                    startOnLoad: false,
                    theme: theme,
                    securityLevel: 'loose',
                    flowchart: { useMaxWidth: false, htmlLabels: true }
                });
            }

            const elements = document.querySelectorAll('.mermaid');
            for (let i = 0; i < elements.length; i++) {
                const el = elements[i];
                if (!el.getAttribute('data-mermaid-code')) {
                    el.setAttribute('data-mermaid-code', el.textContent.trim());
                }
                const code = el.getAttribute('data-mermaid-code');
                
                try {
                    if (window.mermaid) {
                        const { svg } = await window.mermaid.render('rendered-mermaid-' + i, code);
                        el.innerHTML = svg;
                    }
                } catch (err) {
                    el.innerHTML = `<div style="color: var(--accent-error); font-weight: bold; padding: 15px; font-size: 0.85rem;">Diagram Render Error: ${err.message}</div>`;
                }
            }
        }

        function buildTOC() {
            const toc = document.getElementById('toc');
            const headings = document.querySelectorAll('#rendered-content h2, #rendered-content h3');
            
            toc.innerHTML = '';
            
            headings.forEach((heading, idx) => {
                const id = heading.id || 'section-' + idx;
                heading.id = id;

                const level = heading.tagName.toLowerCase() === 'h2' ? 'level-2' : 'level-3';
                
                const li = document.createElement('li');
                li.className = `toc-item ${level}`;
                li.id = 'toc-item-' + id;
                
                const a = document.createElement('a');
                a.href = '#' + id;
                a.textContent = heading.textContent.replace(/^\\d+\\.\\d*\\s*/, '');
                
                li.appendChild(a);
                toc.appendChild(li);
            });

            const pane = document.getElementById('pane');
            pane.addEventListener('scroll', () => {
                let activeId = null;
                const scrollPos = pane.scrollTop + 80;
                
                headings.forEach(heading => {
                    if (heading.offsetTop <= scrollPos) {
                        activeId = heading.id;
                    }
                });

                document.querySelectorAll('.toc-item').forEach(item => item.classList.remove('active'));
                if (activeId) {
                    const activeTOCItem = document.getElementById('toc-item-' + activeId);
                    if (activeTOCItem) activeTOCItem.classList.add('active');
                }
            });
        }

        window.onload = renderDocument;
    </script>
</body>
</html>
"""

    html_content = html_template.replace("_MARKDOWN_SOURCE_PLACEHOLDER_", escaped_md)

    with open(output_html, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"Successfully generated full interactive rendered report to {output_html}.")

if __name__ == "__main__":
    main()
