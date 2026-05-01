import click
import humanize
from pathlib import Path
from rich.progress import Progress
from rich.table import Table
from cloudmesh.ai.common.io import console
from cloudmesh.ai.storage.storage_manager import StorageManager
from cloudmesh.ai.command.storage_view import StorageInfoView

@click.group(name="storage")
def storage_group():
    """
    Storage utilities for finding equivalent directory trees.
    """
    pass

@storage_group.command(name="equiv")
@click.option("--dir", "root_dir", type=click.Path(), required=True, help="Root directory to search from.")
def equiv_cmd(root_dir):
    """
    Find equivalent directory trees on a file system.
    """
    root = Path(root_dir).expanduser().absolute()
    console.banner(f"Searching for equivalent directories under: {root}")
    
    manager = StorageManager()
    
    with Progress(console=console) as progress:
        scan_task = progress.add_task("[cyan]Scanning file system...", total=None)
        compare_task = progress.add_task("[magenta]Comparing directories...", total=None)

        def on_scan(n):
            progress.update(scan_task, advance=n)

        def on_compare(n):
            progress.update(compare_task, advance=n)

        def on_match(name, group):
            console.ok(f"Found {len(group)} equivalent directories for '{name}': {group[0]} ...")

        manager.find_equivalent_directories(
            root_dir=root,
            on_scan_progress=on_scan,
            on_compare_progress=on_compare,
            on_match_found=on_match
        )

    # Print summary table of results
    try:
        import yaml
        config_path = Path.home() / ".config" / "cloudmesh" / "storage" / "equivalencies.yaml"
        if config_path.exists():
            with open(config_path, "r") as f:
                data = yaml.safe_load(f)
                candidates = data.get("candidates", {}) if isinstance(data, dict) else {}
                
                if candidates:
                    console.banner("Equivalent Directories Summary")
                    
                    # Group by metrics to show equivalencies
                    metrics_map = {}
                    for dirname, paths_meta in candidates.items():
                        if not isinstance(paths_meta, dict): continue
                        for path, meta in paths_meta.items():
                            if not isinstance(meta, dict): continue
                            metrics = (meta.get("size", 0), meta.get("files", 0), meta.get("dirs", 0))
                            if metrics not in metrics_map:
                                metrics_map[metrics] = []
                            metrics_map[metrics].append((dirname, path, meta))
                    
                    for i, (metrics, members) in enumerate(metrics_map.items(), 1):
                        if len(members) < 2: continue # Only show actual equivalencies
                        
                        size, files, dirs = metrics
                        table = Table(title=f"Group {i} ({humanize.naturalsize(size)}, {files} files, {dirs} dirs)")
                        table.add_column("Dirname", style="cyan")
                        table.add_column("Path", style="magenta")
                        table.add_column("Size", style="green")
                        
                        for dirname, path, meta in members:
                            table.add_row(dirname, path, humanize.naturalsize(meta.get("size", 0)))
                        console.print(table)
                        console.print()
    except Exception as e:
        console.print(f"[red]Could not print summary table: {e}[/red]")

    console.ok("Search complete. Results saved to ~/.config/cloudmesh/storage/equivalencies.yaml")

@storage_group.command(name="view")
def view_cmd():
    """
    Open the interactive browser view of storage equivalencies.
    """
    view = StorageInfoView()
    view.open_in_browser()
    console.ok("Opened storage info view in browser.")

@storage_group.command(name="candidate")
@click.argument("dirname")
@click.option("--dir", "root_dir", type=click.Path(), default=".", help="Root directory to search from.")
def candidate_cmd(dirname, root_dir):
    """
    Find all directories with the specified basename.
    """
    root = Path(root_dir).expanduser().absolute()
    console.banner(f"Searching for directories named '{dirname}' under: {root}")
    
    manager = StorageManager()
    matches = manager.find_directories_by_name(root, dirname)
    
    if not matches:
        console.warning(f"No directories named '{dirname}' found.")
    else:
        console.print(f"Found {len(matches)} matches:")
        for path in sorted(matches):
            console.print(f"- {path}")
        
        # Save initial candidates to YAML
        manager.save_candidates(dirname, [str(p) for p in matches])
        console.ok(f"Candidates for '{dirname}' saved to ~/.config/cloudmesh/storage/equivalencies.yaml")

        # Ask if user wants to determine metadata (size, file/dir counts)
        if click.confirm("\nWould you like to determine the size and content of these directories?", default=True):
            console.banner(f"Calculating metadata for {len(matches)} directories...")
            
            candidates_metadata = {}
            metadata_groups = {}
            
            for path in matches:
                meta = manager.get_dir_metadata(path)
                size = meta["size"]
                files = meta["files"]
                dirs = meta["dirs"]
                
                # Use humanize for professional size formatting
                size_str = humanize.naturalsize(size) if size >= 0 else "Error"
                
                console.print(f"- {path}: {size_str} ({files} files, {dirs} dirs)")
                
                # Store full metadata in YAML
                candidates_metadata[str(path)] = meta
                
                # Group by size, file count, and dir count for "guessing" phase
                if size >= 0:
                    # Use a tuple of (size, files, dirs) as the key for more accurate grouping
                    group_key = (size, files, dirs)
                    if group_key not in metadata_groups:
                        metadata_groups[group_key] = []
                    metadata_groups[group_key].append(str(path))
            
            # Update YAML with full metadata
            manager.save_candidates(dirname, candidates_metadata)
            console.ok("Directory metadata calculated and saved to YAML.")

            # Guessing phase: Group by size and content
            potential_groups = [paths for key, paths in metadata_groups.items() if len(paths) > 1]
            unique_dirs = [paths[0] for key, paths in metadata_groups.items() if len(paths) == 1]

            if potential_groups:
                console.banner("Potential Equivalents (Based on Size and Content)")
                for i, group in enumerate(potential_groups, 1):
                    first_path = Path(group[0])
                    meta = manager.get_dir_metadata(first_path)
                    
                    table = Table(title=f"Group {i} ({humanize.naturalsize(meta['size'])}, {meta['files']} files, {meta['dirs']} dirs)")
                    table.add_column("Path", style="cyan")
                    table.add_column("Size", style="magenta")
                    table.add_column("Files", style="green")
                    table.add_column("Dirs", style="yellow")
                    
                    for p in group:
                        # We can use the metadata we already have in candidates_metadata
                        p_meta = candidates_metadata.get(p, {})
                        table.add_row(
                            p, 
                            humanize.naturalsize(p_meta.get("size", 0)), 
                            str(p_meta.get("files", 0)), 
                            str(p_meta.get("dirs", 0))
                        )
                    console.print(table)
                    console.print()
            
            if unique_dirs:
                console.banner("Unique Directories (No size/content match)")
                table = Table()
                table.add_column("Path", style="cyan")
                table.add_column("Size", style="magenta")
                table.add_column("Files", style="green")
                table.add_column("Dirs", style="yellow")
                
                for p in sorted(unique_dirs):
                    p_meta = candidates_metadata.get(p, {})
                    table.add_row(
                        p, 
                        humanize.naturalsize(p_meta.get("size", 0)), 
                        str(p_meta.get("files", 0)), 
                        str(p_meta.get("dirs", 0))
                    )
                console.print(table)
            
            if not potential_groups and not unique_dirs:
                console.print("\nNo metadata found to group.")

            # Open the interactive browser view
            if click.confirm("\nWould you like to open the interactive browser view?", default=True):
                view = StorageInfoView()
                view.open_in_browser()
                console.ok("Opened storage info view in browser.")

def register(cli):
    """
    Registers the storage commands with the main CLI.
    """
    cli.add_command(storage_group)
