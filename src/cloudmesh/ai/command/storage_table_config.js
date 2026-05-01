window.StorageTableConfig = {
    formatSize: function(s) {
        if (s === null || s === undefined || s < 0) return 'N/A';
        if (s > 1024 * 1024 * 1024) return (s / (1024 * 1024 * 1024)).toFixed(2) + ' GB';
        if (s > 1024 * 1024) return (s / (1024 * 1024)).toFixed(2) + ' MB';
        if (s > 1024) return (s / 1024).toFixed(2) + ' KB';
        return s + ' B';
    },

    getColumns: function() {
        return [
            { 
                title: "Action", 
                field: "path", 
                width: 120, 
                hozAlign: "center", 
                formatter: function(cell) {
                    const path = cell.getValue();
                    const dirname = cell.getData().dirname;
                     return `<div style="display: flex; gap: 10px; justify-content: center;">
                         <a href="#" onclick="openFolder('${path}')" style="color: #0969da; text-decoration: none;" title="Open in Terminal">
                             <i class="fas fa-folder-open"></i>
                         </a>
                         <a href="#" onclick="downloadStorage('${path}')" style="color: #059669; text-decoration: none;" title="Download Path Info">
                             <i class="fas fa-download"></i>
                         </a>
                         <a href="#" onclick="deleteFolder('${path}', '${dirname}')" style="color: #cf222e; text-decoration: none;" title="Delete Directory">
                             <i class="fas fa-trash"></i>
                         </a>
                     </div>`;
                }
            },
            { title: "Dirname", field: "dirname", width: 150 },
            { title: "Path", field: "path", formatter: function(cell) {
                return `<span style="font-family: monospace; font-size: 12px;">${cell.getValue()}</span>`;
            }},
            { title: "Exclude", field: "exclude", width: 120, editor: "input" },
            { title: "Search", field: "search", width: 120, editor: "input" },
            { title: "Size", field: "size", width: 200, hozAlign: "right", formatter: (cell) => StorageTableConfig.formatSize(cell.getValue()) },
            { title: "Files", field: "files", width: 150, hozAlign: "right" },
            { title: "Dirs", field: "dirs", width: 150, hozAlign: "right" },
        ];
    },

    render: function(elementId, data) {
        console.log(`[StorageTableConfig] Rendering table in ${elementId} with ${data ? data.length : 0} rows`);
        try {
            if (typeof Tabulator === 'undefined') {
                throw new Error("Tabulator library is not loaded");
            }

            const container = document.querySelector(elementId);
            if (!container) throw new Error(`Element ${elementId} not found`);
            
            container.innerHTML = ''; // Clear existing content
            
            // Create Filter Bar
            const filterBar = document.createElement('div');
            filterBar.className = 'flex gap-4 p-3 bg-gray-50 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700';
            filterBar.innerHTML = `
                <div class="flex items-center gap-2">
                    <span class="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase">Search:</span>
                    <input type="text" id="storage-search" class="px-2 py-1 text-sm border rounded focus:ring-2 focus:ring-blue-500 outline-none bg-white dark:bg-gray-700 border-gray-300 dark:border-gray-600 text-gray-900 dark:text-white" placeholder="Filter paths...">
                </div>
                <div class="flex items-center gap-2">
                    <span class="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase">Exclude:</span>
                    <input type="text" id="storage-exclude" class="px-2 py-1 text-sm border rounded focus:ring-2 focus:ring-blue-500 outline-none bg-white dark:bg-gray-700 border-gray-300 dark:border-gray-600 text-gray-900 dark:text-white" placeholder="Exclude patterns...">
                </div>
            `;
            
            // Create Table Element
            const tableEl = document.createElement('div');
            tableEl.className = 'flex-1 h-full';
            
            container.appendChild(filterBar);
            container.appendChild(tableEl);
            
            const table = new Tabulator(tableEl, {
                data: data,
                layout: "fitColumns",
                height: "100%",
                groupBy: "group",
                groupHeader: function(value, count, data, group) {
                    return `<span style="color: #0969da; font-weight: 600; font-size: 16px;">${value} (${count} directories)</span>`;
                },
                columns: this.getColumns(),
            });

            // Filter Logic
            const applyFilters = () => {
                const searchVal = document.getElementById('storage-search')?.value || '';
                const excludeVal = document.getElementById('storage-exclude')?.value || '';
                
                table.setFilter(function(data) {
                    const path = data.path || '';
                    
                    // Exclude supersedes search: if it matches exclude, it's hidden immediately
                    if (excludeVal && path.toLowerCase().includes(excludeVal.toLowerCase())) {
                        return false;
                    }
                    
                    // Then apply search filter
                    if (searchVal && !path.toLowerCase().includes(searchVal.toLowerCase())) {
                        return false;
                    }
                    
                    return true;
                });
            };

            container.addEventListener('input', (e) => {
                if (e.target.id === 'storage-search' || e.target.id === 'storage-exclude') {
                    applyFilters();
                }
            });

            console.log("[StorageTableConfig] Tabulator instance created successfully with filters");
            return table;
        } catch (e) {
            console.error("[StorageTableConfig] Render error:", e);
            throw e;
        }
    }
};