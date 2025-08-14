// CodeClash Trajectory Viewer - JavaScript Controls

// Theme management
function initializeTheme() {
    // Check for saved theme preference or default to 'light'
    const savedTheme = localStorage.getItem('theme') || 'light';
    setTheme(savedTheme);
}

function setTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);

    // Update theme toggle button
    const themeToggle = document.getElementById('theme-toggle');
    const themeIcon = themeToggle.querySelector('.theme-icon');

    if (theme === 'dark') {
        themeIcon.textContent = '☀️';
        themeToggle.setAttribute('aria-label', 'Switch to light mode');
    } else {
        themeIcon.textContent = '🌙';
        themeToggle.setAttribute('aria-label', 'Switch to dark mode');
    }
}

function toggleTheme() {
    const currentTheme = document.documentElement.getAttribute('data-theme');
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    setTheme(newTheme);
}

// Folder selection
function changeFolder() {
    const select = document.getElementById('folder-select');
    const selectedFolder = select.value;

    if (selectedFolder) {
        // Reload page with new folder parameter
        const url = new URL(window.location);
        url.searchParams.set('folder', selectedFolder);
        window.location.href = url.toString();
    }
}

// Enhanced foldout behavior
function initializeFoldouts() {
    // Add smooth animations to details elements
    const detailsElements = document.querySelectorAll('details');

    detailsElements.forEach(details => {
        const summary = details.querySelector('summary');

        // Add click analytics/feedback
        summary.addEventListener('click', function(e) {
            // Small delay to allow default behavior
            setTimeout(() => {
                // Scroll into view if needed
                if (details.open) {
                    const rect = details.getBoundingClientRect();
                    const isInViewport = rect.top >= 0 && rect.bottom <= window.innerHeight;

                    if (!isInViewport) {
                        details.scrollIntoView({
                            behavior: 'smooth',
                            block: 'nearest'
                        });
                    }
                }
            }, 100);
        });
    });
}

// Keyboard shortcuts
function initializeKeyboardShortcuts() {
    document.addEventListener('keydown', function(e) {
        // Ctrl/Cmd + D: Toggle dark mode
        if ((e.ctrlKey || e.metaKey) && e.key === 'd') {
            e.preventDefault();
            toggleTheme();
        }

        // Escape: Close all open details
        if (e.key === 'Escape') {
            const openDetails = document.querySelectorAll('details[open]');
            openDetails.forEach(details => {
                details.removeAttribute('open');
            });
        }

        // Ctrl/Cmd + E: Expand all details
        if ((e.ctrlKey || e.metaKey) && e.key === 'e') {
            e.preventDefault();
            const allDetails = document.querySelectorAll('details');
            allDetails.forEach(details => {
                details.setAttribute('open', '');
            });
        }

        // Ctrl/Cmd + Shift + E: Collapse all details
        if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'E') {
            e.preventDefault();
            const allDetails = document.querySelectorAll('details');
            allDetails.forEach(details => {
                details.removeAttribute('open');
            });
        }


    });
}

// Search functionality (basic)
function initializeSearch() {
    // Add search input to header if it doesn't exist
    const controls = document.querySelector('.controls');
    if (controls && !document.getElementById('search-input')) {
        const searchGroup = document.createElement('div');
        searchGroup.className = 'control-group';

        const searchLabel = document.createElement('label');
        searchLabel.setAttribute('for', 'search-input');
        searchLabel.textContent = 'Search:';

        const searchInput = document.createElement('input');
        searchInput.type = 'text';
        searchInput.id = 'search-input';
        searchInput.placeholder = 'Search messages...';
        searchInput.style.padding = '0.5rem';
        searchInput.style.border = '1px solid var(--border-color)';
        searchInput.style.borderRadius = '0.375rem';
        searchInput.style.backgroundColor = 'var(--bg-primary)';
        searchInput.style.color = 'var(--text-primary)';
        searchInput.style.fontSize = '0.875rem';
        searchInput.style.minWidth = '200px';

        searchGroup.appendChild(searchLabel);
        searchGroup.appendChild(searchInput);
        controls.insertBefore(searchGroup, controls.lastElementChild);

        // Add search functionality
        let searchTimeout;
        searchInput.addEventListener('input', function(e) {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {
                performSearch(e.target.value);
            }, 300);
        });
    }
}

function performSearch(searchTerm) {
    const messages = document.querySelectorAll('.message-content');
    const highlights = document.querySelectorAll('.search-highlight');

    // Clear previous highlights
    highlights.forEach(highlight => {
        const parent = highlight.parentNode;
        parent.replaceChild(document.createTextNode(highlight.textContent), highlight);
        parent.normalize();
    });

    if (!searchTerm.trim()) {
        return;
    }

    const regex = new RegExp(`(${escapeRegExp(searchTerm)})`, 'gi');

    messages.forEach(messageContent => {
        const textNodes = getTextNodes(messageContent);
        textNodes.forEach(node => {
            if (regex.test(node.textContent)) {
                const parent = node.parentNode;
                const highlighted = node.textContent.replace(regex, '<mark class="search-highlight">$1</mark>');
                const wrapper = document.createElement('span');
                wrapper.innerHTML = highlighted;
                parent.replaceChild(wrapper, node);

                // Open the containing details if closed
                let detailsParent = parent.closest('details');
                while (detailsParent) {
                    detailsParent.setAttribute('open', '');
                    detailsParent = detailsParent.parentElement.closest('details');
                }
            }
        });
    });
}

function getTextNodes(element) {
    const textNodes = [];
    const walker = document.createTreeWalker(
        element,
        NodeFilter.SHOW_TEXT,
        null,
        false
    );

    let node;
    while (node = walker.nextNode()) {
        textNodes.push(node);
    }

    return textNodes;
}

function escapeRegExp(string) {
    return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

// Code highlighting (basic syntax highlighting)
function initializeCodeHighlighting() {
    const codeBlocks = document.querySelectorAll('.code-block code, .message-text pre');

    codeBlocks.forEach(block => {
        const text = block.textContent;

        // Simple bash highlighting
        if (text.includes('#!/bin/bash') || text.includes('```bash')) {
            block.classList.add('language-bash');
            highlightBash(block);
        }

        // Simple Python highlighting
        if (text.includes('def ') || text.includes('import ') || text.includes('python')) {
            block.classList.add('language-python');
            highlightPython(block);
        }
    });
}

function highlightBash(block) {
    let html = block.innerHTML;

    // Commands
    html = html.replace(/\b(ls|cd|cat|grep|sed|awk|find|mkdir|rm|cp|mv|chmod|echo|export)\b/g,
        '<span style="color: var(--accent-color); font-weight: 600;">$1</span>');

    // Flags
    html = html.replace(/\s(-[a-zA-Z]+)/g,
        ' <span style="color: var(--warning-color);">$1</span>');

    block.innerHTML = html;
}

function highlightPython(block) {
    let html = block.innerHTML;

    // Keywords
    html = html.replace(/\b(def|class|import|from|if|else|elif|for|while|try|except|finally|return|yield|with|as|pass|break|continue|lambda|global|nonlocal)\b/g,
        '<span style="color: var(--accent-color); font-weight: 600;">$1</span>');

    // Strings
    html = html.replace(/(["'])((?:\\.|(?!\1)[^\\])*?)\1/g,
        '<span style="color: var(--success-color);">$1$2$1</span>');

    block.innerHTML = html;
}

// Performance monitoring
function initializePerformanceMonitoring() {
    // Log page load time
    window.addEventListener('load', function() {
        const loadTime = performance.now();
        console.log(`Page loaded in ${loadTime.toFixed(2)}ms`);

        // Count elements for performance insight
        const messageCount = document.querySelectorAll('.message-block').length;
        const foldoutCount = document.querySelectorAll('details').length;

        console.log(`Rendered ${messageCount} messages and ${foldoutCount} foldouts`);
    });
}

// Message expand/collapse functionality
function toggleMessageExpand(clickedElement) {
    const messageHeader = clickedElement.closest('.message-header');
    const previewShort = messageHeader.querySelector('.message-preview-short');
    const contentFull = messageHeader.querySelector('.message-content-full');
    const contentExpanded = messageHeader.querySelector('.message-content-expanded');

    if (clickedElement.classList.contains('message-preview-short')) {
        // Expanding - hide preview, show full content
        if (previewShort) previewShort.style.display = 'none';
        if (contentFull) contentFull.style.display = 'block';
        if (contentExpanded) contentExpanded.style.display = 'block';

        // Smooth scroll to keep the content in view
        setTimeout(() => {
            messageHeader.scrollIntoView({
                behavior: 'smooth',
                block: 'nearest'
            });
        }, 100);
    } else if (clickedElement.classList.contains('message-content-full') || clickedElement.classList.contains('message-content-expanded')) {
        // Collapsing - show preview, hide full content
        if (contentFull) contentFull.style.display = 'none';
        if (contentExpanded) contentExpanded.style.display = 'none';
        if (previewShort) previewShort.style.display = 'block';

        // Smooth scroll to keep the header in view
        setTimeout(() => {
            messageHeader.scrollIntoView({
                behavior: 'smooth',
                block: 'nearest'
            });
        }, 100);
    }
}



// Initialize everything when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    initializeTheme();
    initializeFoldouts();
    initializeKeyboardShortcuts();
    initializeSearch();
    initializeCodeHighlighting();
    initializePerformanceMonitoring();

    console.log('CodeClash Trajectory Viewer initialized');
    console.log('Keyboard shortcuts:');
    console.log('  Ctrl/Cmd + D: Toggle dark mode');
    console.log('  Ctrl/Cmd + E: Expand all sections');
    console.log('  Ctrl/Cmd + Shift + E: Collapse all sections');
    console.log('  Escape: Close all sections');
});
