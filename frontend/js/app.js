// No hardcoded themes — loaded from /api/themes at runtime

// Configure marked
marked.use({
    breaks: true,
    gfm: true,
});

// Mermaid init
mermaid.initialize({ startOnLoad: false, theme: 'dark' });

function noteApp() {
    return {
        // State
        user: null,
        fileTree: [],
        currentNote: null,
        editorContent: '',
        renderedContent: '',
        unsaved: false,
        viewMode: 'split',
        sidebarPanel: 'files',
        sidebarWidth: 280,
        showGraph: false,
        showNewNote: false,
        showNewFolder: false,
        showQuickSwitch: false,
        showRename: false,
        renameValue: '',
        newNoteName: '',
        newFolderName: '',
        targetFolder: '',
        expandedFolders: {},
        searchQuery: '',
        searchResults: [],
        allTags: [],
        selectedTags: [],
        outline: [],
        allNotes: [],
        quickSwitchQuery: '',
        quickSwitchFiltered: [],
        quickSwitchIdx: 0,
        _resizing: false,
        _saveTimeout: null,
        showShare: false,
        shareInfo: null,
        shareLoading: false,
        shareCopied: false,
        _sharedPaths: new Set(),

        // Themes (loaded from API)
        availableThemes: [],
        currentTheme: localStorage.getItem('izoldian-theme') || 'dark',

        // Locales (loaded from API)
        availableLocales: [],
        translations: {},
        currentLocale: localStorage.getItem('izoldian-locale') || 'en-US',

        // Settings dialog
        showSettings: false,

        // Mobile
        isMobile: false,
        sidebarOpen: false,

        async init() {
            // Check auth
            try {
                const resp = await fetch('/api/auth/me');
                if (!resp.ok) {
                    window.location.href = '/';
                    return;
                }
                this.user = await resp.json();
            } catch (e) {
                window.location.href = '/';
                return;
            }

            // Mobile detection
            const mq = window.matchMedia('(max-width: 767px)');
            this.isMobile = mq.matches;
            if (this.isMobile) this.viewMode = 'preview';
            mq.addEventListener('change', (e) => {
                this.isMobile = e.matches;
                if (e.matches && this.viewMode === 'split') this.viewMode = 'preview';
                if (!e.matches) this.sidebarOpen = false;
            });

            this.setupTreeCallbacks();
            await this.loadThemes();
            await this.loadLocale(this.currentLocale);
            await this.applyTheme(this.currentTheme);
            await this.loadFileTree();
            await this.loadTags();
            await this.loadSharedPaths();
        },

        // --- Themes ---
        async loadThemes() {
            try {
                const resp = await fetch('/api/themes');
                const data = await resp.json();
                this.availableThemes = data.themes || [];
            } catch (e) {
                console.error('Failed to load themes:', e);
            }
        },

        async setTheme(themeId) {
            this.currentTheme = themeId;
            localStorage.setItem('izoldian-theme', themeId);
            await this.applyTheme(themeId);
        },

        async applyTheme(themeId) {
            try {
                const resp = await fetch(`/api/themes/${themeId}`);
                if (!resp.ok) return;
                const css = await resp.text();

                // Inject CSS into <style> tag
                let styleEl = document.getElementById('theme-styles');
                if (!styleEl) {
                    styleEl = document.createElement('style');
                    styleEl.id = 'theme-styles';
                    document.head.appendChild(styleEl);
                }
                styleEl.textContent = css;
                document.documentElement.setAttribute('data-theme', themeId);

                // Update highlight.js theme
                const themeMeta = this.availableThemes.find(t => t.id === themeId);
                const hljsTheme = themeMeta?.hljs || 'github-dark';
                const link = document.getElementById('hljs-theme');
                if (link) {
                    link.href = `https://cdn.jsdelivr.net/npm/highlight.js@11.9.0/styles/${hljsTheme}.min.css`;
                }

                // Update mermaid theme
                const themeType = themeMeta?.type || 'dark';
                mermaid.initialize({ startOnLoad: false, theme: themeType === 'light' ? 'default' : 'dark' });

                // Re-render if note open
                if (this.currentNote) {
                    this.$nextTick(() => this.renderMarkdown());
                }
            } catch (e) {
                console.error('Failed to apply theme:', e);
            }
        },

        // --- Locales ---
        async loadLocale(code) {
            try {
                // Load available locales list if not loaded
                if (this.availableLocales.length === 0) {
                    const resp = await fetch('/api/locales');
                    const data = await resp.json();
                    this.availableLocales = data.locales || [];
                }
                // Load translations
                const resp = await fetch(`/api/locales/${code}`);
                if (!resp.ok) return;
                this.translations = await resp.json();
                this.currentLocale = code;
                localStorage.setItem('izoldian-locale', code);
            } catch (e) {
                console.error('Failed to load locale:', e);
            }
        },

        t(key) {
            const parts = key.split('.');
            let val = this.translations;
            for (const p of parts) {
                if (val && typeof val === 'object') val = val[p];
                else return key;
            }
            return val || key;
        },

        toggleSidebar() {
            this.sidebarOpen = !this.sidebarOpen;
        },

        collapseAllFolders() {
            this.expandedFolders = {};
            this.fileTree = [...this.fileTree];
        },

        sidebarTitle() {
            const map = { files: 'sidebar.files', search: 'sidebar.search', tags: 'sidebar.tags', outline: 'sidebar.outline', settings: 'settings.title' };
            return this.t(map[this.sidebarPanel] || 'sidebar.files');
        },

        // File tree
        async loadFileTree() {
            const resp = await fetch('/api/notes');
            const data = await resp.json();
            this.fileTree = data.tree;
            this.allNotes = this.flattenTree(data.tree);
        },

        flattenTree(tree) {
            const result = [];
            for (const item of tree) {
                if (item.type === 'file') {
                    result.push(item);
                } else if (item.children) {
                    result.push(...this.flattenTree(item.children));
                }
            }
            return result;
        },

        // Notes
        async openNote(path) {
            if (this.isMobile) this.sidebarOpen = false;
            if (this.unsaved && this.currentNote) {
                await this.saveNote();
            }

            const resp = await fetch(`/api/notes/by-path/${encodeURIComponent(path)}`);
            if (!resp.ok) return;

            this.currentNote = await resp.json();
            this.editorContent = this.currentNote.content;
            this.unsaved = false;
            this.renderMarkdown();
            this.extractOutline();

            // Focus editor
            this.$nextTick(() => {
                if (this.$refs.editor) this.$refs.editor.focus();
            });
        },

        async saveNote() {
            if (!this.currentNote) return;

            await fetch(`/api/notes/by-path/${encodeURIComponent(this.currentNote.path)}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ content: this.editorContent }),
            });

            this.unsaved = false;
            this.currentNote.content = this.editorContent;
        },

        // --- Format toolbar ---
        formatText(type) {
            const ta = this.$refs.editor;
            if (!ta) return;
            const start = ta.selectionStart;
            const end = ta.selectionEnd;
            const text = this.editorContent;
            const sel = text.substring(start, end);
            const before = text.substring(0, start);
            const after = text.substring(end);

            // Check if at line start
            const lineStart = before.lastIndexOf('\n') + 1;
            const linePrefix = before.substring(lineStart);

            let replacement = '';
            let cursorOffset = 0;

            switch (type) {
                case 'bold':
                    replacement = sel ? `**${sel}**` : '**текст**';
                    cursorOffset = sel ? sel.length + 4 : 2;
                    break;
                case 'italic':
                    replacement = sel ? `*${sel}*` : '*текст*';
                    cursorOffset = sel ? sel.length + 2 : 1;
                    break;
                case 'strikethrough':
                    replacement = sel ? `~~${sel}~~` : '~~текст~~';
                    cursorOffset = sel ? sel.length + 4 : 2;
                    break;
                case 'code':
                    replacement = sel ? `\`${sel}\`` : '`код`';
                    cursorOffset = sel ? sel.length + 2 : 1;
                    break;
                case 'h1':
                    replacement = linePrefix.length === 0 ? `# ${sel || 'Заголовок'}` : `\n# ${sel || 'Заголовок'}`;
                    cursorOffset = replacement.length;
                    break;
                case 'h2':
                    replacement = linePrefix.length === 0 ? `## ${sel || 'Заголовок'}` : `\n## ${sel || 'Заголовок'}`;
                    cursorOffset = replacement.length;
                    break;
                case 'h3':
                    replacement = linePrefix.length === 0 ? `### ${sel || 'Заголовок'}` : `\n### ${sel || 'Заголовок'}`;
                    cursorOffset = replacement.length;
                    break;
                case 'ul':
                    if (sel) {
                        replacement = sel.split('\n').map(l => `- ${l}`).join('\n');
                    } else {
                        replacement = linePrefix.length === 0 ? '- ' : '\n- ';
                    }
                    cursorOffset = replacement.length;
                    break;
                case 'ol':
                    if (sel) {
                        replacement = sel.split('\n').map((l, i) => `${i + 1}. ${l}`).join('\n');
                    } else {
                        replacement = linePrefix.length === 0 ? '1. ' : '\n1. ';
                    }
                    cursorOffset = replacement.length;
                    break;
                case 'checklist':
                    if (sel) {
                        replacement = sel.split('\n').map(l => `- [ ] ${l}`).join('\n');
                    } else {
                        replacement = linePrefix.length === 0 ? '- [ ] ' : '\n- [ ] ';
                    }
                    cursorOffset = replacement.length;
                    break;
                case 'blockquote':
                    if (sel) {
                        replacement = sel.split('\n').map(l => `> ${l}`).join('\n');
                    } else {
                        replacement = linePrefix.length === 0 ? '> ' : '\n> ';
                    }
                    cursorOffset = replacement.length;
                    break;
                case 'link':
                    replacement = sel ? `[${sel}](url)` : '[текст](url)';
                    cursorOffset = sel ? sel.length + 2 : 1;
                    break;
                case 'image':
                    replacement = sel ? `![${sel}](url)` : '![описание](url)';
                    cursorOffset = sel ? sel.length + 3 : 2;
                    break;
                case 'table':
                    replacement = (linePrefix.length === 0 ? '' : '\n') + '| Заголовок 1 | Заголовок 2 | Заголовок 3 |\n| --- | --- | --- |\n| ячейка | ячейка | ячейка |\n';
                    cursorOffset = replacement.length;
                    break;
                case 'codeblock':
                    replacement = (linePrefix.length === 0 ? '' : '\n') + '```\n' + (sel || 'код') + '\n```\n';
                    cursorOffset = (linePrefix.length === 0 ? 4 : 5);
                    break;
                case 'hr':
                    replacement = (linePrefix.length === 0 ? '' : '\n') + '\n---\n';
                    cursorOffset = replacement.length;
                    break;
            }

            // Use setRangeText to preserve scroll position
            ta.focus();
            ta.setRangeText(replacement, start, end, 'end');
            const pos = start + cursorOffset;
            ta.setSelectionRange(pos, pos);
            const scrollTop = ta.scrollTop;
            // Sync Alpine model from DOM value
            this.editorContent = ta.value;
            // Restore scroll after Alpine re-renders
            this.$nextTick(() => {
                ta.scrollTop = scrollTop;
                ta.setSelectionRange(pos, pos);
            });
            // Trigger save & preview without re-triggering full autoSave debounce
            this.unsaved = true;
            this.renderMarkdown();
            this.extractOutline();
            clearTimeout(this._saveTimeout);
            this._saveTimeout = setTimeout(() => this.saveNote(), 1500);
        },

        autoSave() {
            this.unsaved = true;
            this.renderMarkdown();
            this.extractOutline();

            clearTimeout(this._saveTimeout);
            this._saveTimeout = setTimeout(() => this.saveNote(), 1500);
        },

        async deleteCurrentNote() {
            if (!this.currentNote) return;
            if (!confirm(this.t('notes.delete_confirm').replace('{name}', this.currentNote.name))) return;

            await fetch(`/api/notes/by-path/${encodeURIComponent(this.currentNote.path)}`, { method: 'DELETE' });
            this.currentNote = null;
            this.editorContent = '';
            this.renderedContent = '';
            await this.loadFileTree();
        },

        // --- File tree rendering (recursive) ---
        renderFileTreeHTML(items, depth) {
            try {
                return this._buildTreeHTML(items || [], depth || 0);
            } catch (e) {
                console.error('renderFileTreeHTML error:', e);
                return '<div class="text-red-400 text-xs p-2">Ошибка рендеринга дерева</div>';
            }
        },

        _esc(str) {
            return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/'/g, '&#39;').replace(/"/g, '&quot;');
        },

        _buildTreeHTML(items, depth) {
            if (!items || items.length === 0) return '';
            var html = '';
            for (var i = 0; i < items.length; i++) {
                var item = items[i];
                var epath = this._esc(item.path);
                var ename = this._esc(item.name);
                if (item.type === 'folder') {
                    var expanded = this.expandedFolders[item.path] === true;
                    var chevron = expanded ? 'transform rotate-90' : '';
                    var childStyle = expanded ? '' : 'display:none';
                    html += '<div>';
                    html += '<div class="group flex items-center gap-1.5 px-2 py-1.5 rounded cursor-pointer hover:bg-gray-800 text-gray-400 text-sm" onclick="window._treeToggle(\x27' + epath + '\x27)">';
                    html += '<svg class="w-4 h-4 shrink-0 transition-transform ' + chevron + '" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/></svg>';
                    html += '<svg class="w-5 h-5 shrink-0 text-yellow-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"/></svg>';
                    html += '<span class="truncate flex-1">' + ename + '</span>';
                    html += '<span class="hidden group-hover:flex items-center gap-1 shrink-0" onclick="event.stopPropagation()">';
                    html += '<button class="text-gray-600 hover:text-gray-300 p-0.5" onclick="window._treeNewNote(\x27' + epath + '\x27)" title="Новая заметка"><svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/></svg></button>';
                    html += '<button class="text-gray-600 hover:text-gray-300 p-0.5" onclick="window._treeNewFolder(\x27' + epath + '\x27)" title="Новая папка"><svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 13h6m-3-3v6m-9 1V7a2 2 0 012-2h6l2 2h6a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2z"/></svg></button>';
                    html += '<button class="text-gray-600 hover:text-red-400 p-0.5" onclick="window._treeDeleteFolder(\x27' + epath + '\x27)" title="Удалить папку"><svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg></button>';
                    html += '</span>';
                    html += '</div>';
                    html += '<div class="ml-4" style="' + childStyle + '">';
                    html += this._buildTreeHTML(item.children || [], depth + 1);
                    html += '</div></div>';
                } else {
                    var active = this.currentNote && this.currentNote.path === item.path;
                    var cls = active ? 'bg-blue-900/30 text-blue-300' : 'text-gray-400 hover:bg-gray-800 hover:text-gray-200';
                    html += '<div onclick="window._treeOpenNote(\x27' + epath + '\x27)" class="flex items-center gap-2 px-2 py-1.5 rounded cursor-pointer text-sm transition ' + cls + '">';
                    html += '<svg class="w-5 h-5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>';
                    html += '<span class="truncate flex-1">' + ename + '</span>';
                    if (this._sharedPaths.has(item.path)) {
                        html += '<svg class="w-3.5 h-3.5 shrink-0 text-green-500" title="Расшарено" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z"/></svg>';
                    }
                    html += '</div>';
                }
            }
            return html;
        },

        setupTreeCallbacks() {
            const app = this;
            window._treeOpenNote = (path) => app.openNote(path);
            window._treeToggle = (path) => {
                app.expandedFolders[path] = !app.expandedFolders[path];
                // Force re-render of tree
                app.fileTree = [...app.fileTree];
            };
            window._treeNewNote = (folderPath) => app.showNewNoteDialog(folderPath);
            window._treeNewFolder = (folderPath) => app.showNewFolderDialog(folderPath);
            window._treeDeleteFolder = async (folderPath) => {
                if (!confirm(app.t('folders.delete_confirm').replace('{name}', folderPath))) return;
                const resp = await fetch('/api/folders/' + encodeURIComponent(folderPath), { method: 'DELETE' });
                if (resp.ok) await app.loadFileTree();
            };
        },

        // --- New Note ---
        showNewNoteDialog(folder) {
            this.targetFolder = folder || '';
            this.showNewNote = true;
            this.newNoteName = '';
            this.$nextTick(() => this.$refs.newNoteInput?.focus());
        },

        async createNewNote() {
            if (!this.newNoteName.trim()) return;

            let name = this.newNoteName.trim();
            if (!name.endsWith('.md')) name += '.md';
            const path = this.targetFolder ? this.targetFolder + '/' + name : name;

            await fetch(`/api/notes/by-path/${encodeURIComponent(path)}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ content: `# ${this.newNoteName.trim()}\n\n` }),
            });

            this.showNewNote = false;
            await this.loadFileTree();
            await this.openNote(path);
        },

        // --- New Folder ---
        showNewFolderDialog(parentFolder) {
            this.targetFolder = parentFolder || '';
            this.showNewFolder = true;
            this.newFolderName = '';
            this.$nextTick(() => this.$refs.newFolderInput?.focus());
        },

        async createNewFolder() {
            if (!this.newFolderName.trim()) return;

            const name = this.newFolderName.trim();
            const path = this.targetFolder ? this.targetFolder + '/' + name : name;

            await fetch('/api/folders', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path: path }),
            });

            this.showNewFolder = false;
            // Auto-expand parent
            if (this.targetFolder) {
                this.expandedFolders[this.targetFolder] = true;
            }
            await this.loadFileTree();
        },

        // --- Rename ---
        showRenameDialog() {
            if (!this.currentNote) return;
            this.renameValue = this.currentNote.name;
            this.showRename = true;
            this.$nextTick(() => {
                const input = this.$refs.renameInput;
                if (input) { input.focus(); input.select(); }
            });
        },

        async renameNote() {
            if (!this.renameValue.trim() || !this.currentNote) return;

            let newName = this.renameValue.trim();
            if (!newName.endsWith('.md')) newName += '.md';

            const oldPath = this.currentNote.path;
            const dir = oldPath.includes('/') ? oldPath.substring(0, oldPath.lastIndexOf('/') + 1) : '';
            const newPath = dir + newName;

            if (newPath === oldPath) {
                this.showRename = false;
                return;
            }

            const resp = await fetch('/api/notes/move', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ source: oldPath, destination: newPath }),
            });

            if (resp.ok) {
                this.showRename = false;
                this.unsaved = false; // prevent saveNote to old path
                this.currentNote = null;
                await this.loadFileTree();
                await this.openNote(newPath);
            }
        },

        // --- Sharing ---
        async loadSharedPaths() {
            try {
                const resp = await fetch('/api/shared-notes');
                const data = await resp.json();
                this._sharedPaths = new Set(data.paths || []);
            } catch (e) {}
        },

        isNoteShared(path) {
            return this._sharedPaths.has(path);
        },

        async openShareDialog() {
            if (!this.currentNote) return;
            this.showShare = true;
            this.shareInfo = null;
            this.shareCopied = false;
            this.shareLoading = true;
            try {
                const resp = await fetch(`/api/share/info/${encodeURIComponent(this.currentNote.path)}`);
                this.shareInfo = await resp.json();
            } catch (e) {}
            this.shareLoading = false;
        },

        async createShareLink() {
            if (!this.currentNote) return;
            this.shareLoading = true;
            try {
                const resp = await fetch(`/api/share/${encodeURIComponent(this.currentNote.path)}`, { method: 'POST' });
                const data = await resp.json();
                this.shareInfo = { shared: true, token: data.token, url: data.url };
                this._sharedPaths.add(this.currentNote.path);
                this.fileTree = [...this.fileTree]; // re-render tree for share indicator
                await this.copyShareLink();
            } catch (e) {}
            this.shareLoading = false;
        },

        async copyShareLink() {
            if (!this.shareInfo || !this.shareInfo.url) return;
            try {
                await navigator.clipboard.writeText(this.shareInfo.url);
                this.shareCopied = true;
                setTimeout(() => { this.shareCopied = false; }, 2000);
            } catch (e) {}
        },

        async revokeShareLink() {
            if (!this.currentNote || !this.shareInfo) return;
            if (!confirm(this.t('share.revoke_confirm'))) return;
            try {
                await fetch(`/api/share/${encodeURIComponent(this.currentNote.path)}`, { method: 'DELETE' });
                this._sharedPaths.delete(this.currentNote.path);
                this.shareInfo = { shared: false };
                this.fileTree = [...this.fileTree];
            } catch (e) {}
        },

        // Markdown rendering
        renderMarkdown() {
            let content = this.editorContent;

            // Strip frontmatter for rendering
            if (content.startsWith('---')) {
                const parts = content.split('---');
                if (parts.length >= 3) {
                    content = parts.slice(2).join('---').trim();
                }
            }

            // Process wikilinks: [[target|display]] or [[target]]
            content = content.replace(/!\[\[([^\]]+)\]\]/g, (match, target) => {
                // Media wikilink
                const ext = target.split('.').pop().toLowerCase();
                const src = `/api/media/${encodeURIComponent(target)}`;
                if (['png','jpg','jpeg','gif','webp','svg'].includes(ext)) {
                    return `<img src="${src}" alt="${target}" class="max-w-full rounded">`;
                }
                return match;
            });

            content = content.replace(/\[\[([^\]|]+)(?:\|([^\]]+))?\]\]/g, (match, target, display) => {
                const text = display || target;
                return `<a href="#" class="wikilink" data-target="${target}">${text}</a>`;
            });

            // Render markdown
            let html = marked.parse(content);

            // Sanitize
            html = DOMPurify.sanitize(html, {
                ADD_TAGS: ['iframe'],
                ADD_ATTR: ['data-target', 'class', 'id'],
            });

            this.renderedContent = html;

            // Post-render: mermaid, mathjax, wikilink clicks
            this.$nextTick(() => {
                this.postRender();
            });
        },

        async postRender() {
            const preview = this.$refs.preview;
            if (!preview) return;

            // Syntax highlighting + line numbers for code blocks
            preview.querySelectorAll('pre code').forEach(block => {
                if (block.classList.contains('language-mermaid')) return;

                const pre = block.parentElement;
                if (!pre || pre.classList.contains('code-processed')) return;
                pre.classList.add('code-processed', 'code-block');

                // Detect language
                let lang = '';
                for (const cls of block.classList) {
                    if (cls.startsWith('language-')) {
                        lang = cls.replace('language-', '');
                        break;
                    }
                }

                // Highlight: get raw text, run hljs, get HTML with spans
                const rawText = block.textContent;
                let highlighted;
                try {
                    if (lang && hljs.getLanguage(lang)) {
                        highlighted = hljs.highlight(rawText, { language: lang }).value;
                    } else {
                        highlighted = hljs.highlightAuto(rawText).value;
                    }
                } catch (e) {
                    highlighted = block.innerHTML;
                }
                block.classList.add('hljs');

                // Add line numbers — split highlighted HTML preserving spans
                const rawLines = highlighted.split('\n');
                if (rawLines.length > 1 && rawLines[rawLines.length - 1].trim() === '') rawLines.pop();

                let openStack = [];
                block.innerHTML = rawLines.map(function(line, i) {
                    const prefix = openStack.join('');

                    const tagRegex = /<\/?span[^>]*>/g;
                    let m;
                    while ((m = tagRegex.exec(line)) !== null) {
                        if (m[0].startsWith('</')) {
                            openStack.pop();
                        } else {
                            openStack.push(m[0]);
                        }
                    }

                    const suffix = openStack.map(() => '</span>').join('');
                    const content = prefix + line + suffix;
                    return '<span class="code-line"><span class="line-number">' + (i + 1) + '</span><span class="line-content">' + (content || ' ') + '</span></span>';
                }).join('');

                // Wrap pre in container for sticky label
                const wrapper = document.createElement('div');
                wrapper.className = 'code-block-wrapper';
                pre.parentNode.insertBefore(wrapper, pre);
                wrapper.appendChild(pre);

                if (lang) {
                    const label = document.createElement('span');
                    label.className = 'code-lang-label';
                    label.textContent = lang;
                    wrapper.appendChild(label);
                }
            });

            // Mermaid diagrams
            const mermaidBlocks = preview.querySelectorAll('code.language-mermaid');
            for (const block of mermaidBlocks) {
                const pre = block.parentElement;
                const container = document.createElement('div');
                container.className = 'mermaid';
                container.textContent = block.textContent;
                pre.replaceWith(container);
            }
            if (mermaidBlocks.length > 0) {
                try { await mermaid.run({ querySelector: '.mermaid' }); } catch (e) {}
            }

            // MathJax
            if (window.MathJax && MathJax.typesetPromise) {
                try { await MathJax.typesetPromise([preview]); } catch (e) {}
            }

            // Wikilink click handlers
            preview.querySelectorAll('.wikilink').forEach(link => {
                link.addEventListener('click', (e) => {
                    e.preventDefault();
                    const target = link.getAttribute('data-target');
                    this.resolveWikilink(target);
                });
            });
        },

        resolveWikilink(target) {
            // Try to find matching note
            const lower = target.toLowerCase();
            const note = this.allNotes.find(n =>
                n.name.toLowerCase() === lower ||
                n.path.toLowerCase() === lower + '.md' ||
                n.path.toLowerCase() === lower ||
                n.path.toLowerCase().endsWith('/' + lower + '.md')
            );
            if (note) {
                this.openNote(note.path);
            }
        },

        // Outline
        extractOutline() {
            const content = this.editorContent;
            if (!content) { this.outline = []; return; }

            const headings = [];
            const lines = content.split('\n');
            let inFrontmatter = false;
            let inCodeBlock = false;
            let counter = 0;

            for (let i = 0; i < lines.length; i++) {
                const line = lines[i];

                // Frontmatter: only at the very start of the file
                if (i === 0 && line.trim() === '---') {
                    inFrontmatter = true;
                    continue;
                }
                if (inFrontmatter) {
                    if (line.trim() === '---') inFrontmatter = false;
                    continue;
                }

                // Skip fenced code blocks
                if (line.trim().startsWith('```') || line.trim().startsWith('~~~')) {
                    inCodeBlock = !inCodeBlock;
                    continue;
                }
                if (inCodeBlock) continue;

                const match = line.match(/^(#{1,6})\s+(.+)$/);
                if (match) {
                    counter++;
                    headings.push({
                        level: match[1].length,
                        text: match[2].trim(),
                        id: `heading-${counter}`,
                    });
                }
            }
            this.outline = headings;
        },

        scrollToHeading(id) {
            const idx = this.outline.findIndex(h => h.id === id);
            if (idx < 0) return;

            const preview = this.$refs.preview;
            if (!preview) return;

            const headings = preview.querySelectorAll('h1, h2, h3, h4, h5, h6');
            if (headings[idx]) {
                headings[idx].scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        },

        // Search
        async doSearch() {
            if (!this.searchQuery.trim()) {
                this.searchResults = [];
                return;
            }
            const resp = await fetch(`/api/search?q=${encodeURIComponent(this.searchQuery)}`);
            const data = await resp.json();
            this.searchResults = data.results;
        },

        // Tags
        async loadTags() {
            const resp = await fetch('/api/notes/tags');
            const data = await resp.json();
            this.allTags = data.tags;
        },

        toggleTagFilter(tag) {
            const idx = this.selectedTags.indexOf(tag);
            if (idx >= 0) {
                this.selectedTags.splice(idx, 1);
            } else {
                this.selectedTags.push(tag);
            }
        },

        // Graph
        async toggleGraph() {
            this.showGraph = !this.showGraph;
            if (this.showGraph) {
                await this.$nextTick();
                await this.renderGraph();
            }
        },

        async renderGraph() {
            const container = this.$refs.graphContainer;
            if (!container) return;

            const resp = await fetch('/api/graph');
            const data = await resp.json();

            // Read current CSS custom property values
            const cs = getComputedStyle(document.documentElement);
            const themeAccent = cs.getPropertyValue('--accent').trim() || '#3b82f6';
            const themeBorder = cs.getPropertyValue('--border').trim() || '#1f2937';
            const themeTextMuted = cs.getPropertyValue('--text-muted').trim() || '#9ca3af';
            const themeText = cs.getPropertyValue('--text').trim() || '#e5e7eb';

            const nodes = new vis.DataSet(data.nodes.map(n => ({
                id: n.id,
                label: n.label,
                color: {
                    background: n.id === this.currentNote?.path ? themeAccent : themeBorder,
                    border: n.id === this.currentNote?.path ? themeAccent : themeTextMuted,
                    highlight: { background: themeAccent, border: themeAccent },
                },
                font: { color: themeText, size: 12 },
            })));

            const edges = new vis.DataSet(data.edges.map((e, i) => ({
                id: i,
                from: e.from,
                to: e.to,
                color: { color: themeBorder, highlight: themeAccent },
                arrows: 'to',
            })));

            new vis.Network(container, { nodes, edges }, {
                physics: { stabilization: { iterations: 100 } },
                interaction: { hover: true },
                nodes: { shape: 'dot', size: 16 },
                edges: { smooth: { type: 'continuous' } },
            }).on('click', (params) => {
                if (params.nodes.length > 0) {
                    this.openNote(params.nodes[0]);
                    this.showGraph = false;
                }
            });
        },

        // Quick Switcher
        filterQuickSwitch() {
            const q = this.quickSwitchQuery.toLowerCase();
            this.quickSwitchFiltered = q
                ? this.allNotes.filter(n => n.name.toLowerCase().includes(q) || n.path.toLowerCase().includes(q)).slice(0, 20)
                : this.allNotes.slice(0, 20);
            this.quickSwitchIdx = 0;
        },

        selectQuickSwitch() {
            if (this.quickSwitchFiltered[this.quickSwitchIdx]) {
                this.openNote(this.quickSwitchFiltered[this.quickSwitchIdx].path);
                this.showQuickSwitch = false;
            }
        },

        // Sidebar resize
        startResize(e) {
            this._resizing = true;
            const startX = e.clientX;
            const startW = this.sidebarWidth;

            const onMove = (ev) => {
                if (!this._resizing) return;
                this.sidebarWidth = Math.max(180, Math.min(600, startW + ev.clientX - startX));
            };
            const onUp = () => {
                this._resizing = false;
                document.removeEventListener('mousemove', onMove);
                document.removeEventListener('mouseup', onUp);
            };
            document.addEventListener('mousemove', onMove);
            document.addEventListener('mouseup', onUp);
        },

        // Keyboard shortcuts
        handleKeydown(e) {
            if (e.ctrlKey && e.key === 'n') {
                e.preventDefault();
                this.showNewNoteDialog();
            }
            if (e.ctrlKey && e.key === 'p') {
                e.preventDefault();
                this.showQuickSwitch = !this.showQuickSwitch;
                if (this.showQuickSwitch) {
                    this.quickSwitchQuery = '';
                    this.quickSwitchFiltered = this.allNotes.slice(0, 20);
                    this.$nextTick(() => this.$refs.quickSwitchInput?.focus());
                }
            }
            if (e.ctrlKey && e.key === 'b') {
                e.preventDefault();
                this.formatText('bold');
            }
            if (e.ctrlKey && e.key === 'i') {
                e.preventDefault();
                this.formatText('italic');
            }
            if (e.ctrlKey && e.key === 'k') {
                e.preventDefault();
                this.formatText('link');
            }
            if (e.ctrlKey && e.key === 's') {
                e.preventDefault();
                this.saveNote();
            }
            if (e.key === 'F2' && this.currentNote) {
                e.preventDefault();
                this.showRenameDialog();
            }
            if (e.key === 'Escape') {
                this.showNewNote = false;
                this.showNewFolder = false;
                this.showQuickSwitch = false;
                this.showGraph = false;
                this.showRename = false;
                this.showShare = false;
                this.showSettings = false;
            }
        },

        // Auth
        async logout() {
            await fetch('/api/auth/logout', { method: 'POST' });
            window.location.href = '/';
        },
    };
}
