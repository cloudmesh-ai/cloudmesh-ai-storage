const StorageTableConfig = {
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
            { title: "Size", field: "size", width: 200, hozAlign: "right", formatter: (cell) => StorageTableConfig.formatSize(cell.getValue()) },
            { title: "Files", field: "files", width: 150, hozAlign: "right" },
            { title: "Dirs", field: "dirs", width: 150, hozAlign: "right" },
        ];
    },

    render: function(elementId, data) {
        return new Tabulator(elementId, {
            data: data,
            layout: "fitColumns",
            height: "100%",
            groupBy: "group",
            groupHeader: function(value, count, data, group) {
                return `<span style="color: #0969da; font-weight: 600; font-size: 16px;">${value} (${count} directories)</span>`;
            },
            columns: this.getColumns(),
        });
    }
};