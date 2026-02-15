import { ExcelFile } from "@/util/interfaces";
import { FileSpreadsheet, X } from "lucide-react";

// Properties needed for the sidebar file display
interface SidebarFileDisplayProperties {
  files: ExcelFile[];
  onAddFiles: (files: File[]) => void;
  onRemoveFile: (id: string) => void;
}

export function SidebarFileDisplay({
  files,
  onAddFiles,
  onRemoveFile,
}: SidebarFileDisplayProperties) {
  // Handles when a file was dropped in to the drag and drop container
  function handleDrop(event: React.DragEvent): void {
    event.preventDefault();
    const droppedFiles = Array.from(event.dataTransfer.files); // TODO: THIS IS CURRENTLY BROKEN AND DOES NOT WORK! <--- pls fix
    onAddFiles(droppedFiles);
  }

  // Makes the drag & drop functionality work properly
  function handleDragOver(event: React.DragEvent): void {
    event.preventDefault();
  }

  // Makes the drag & drop functionality work properly
  function handleDragLeave(event: React.DragEvent): void {
    event.preventDefault();
  }

  // Renders an empty state with drag & drop instructions
  function renderEmptyState() {
    return (
      <div className="text-center p-5">
        <div className="w-10 h-10 rounded-lg bg-gray-800/50 flex items-center justify-center mx-auto mb-2">
          <FileSpreadsheet size={20} className="text-gray-600" />
        </div>
        {/* Display drag & drop instructions */}
        <p className="text-xs text-gray-500">No files uploaded</p>
        <p className="text-xs text-gray-500">Drag & drop here</p>
      </div>
    );
  }

  // Renders the full file list with all currently active files
  function renderFileList() {
    return (
      <div>
        {/* List of all files */}
        {files.map((file) => (
          <div
            key={file.id}
            className="flex items-center gap-2 p-2 rounded-lg bg-gray-800/80 border border-gray-700/30 hover:border-green-600/30"
          >
            {/* File index */}
            <div className="w-5 h-5 rounded bg-green-600/20 flex items-center justify-center text-xs font-bold text-green-400">
              {file.index}
            </div>

            {/* File name */}
            <div className="flex-1 min-w-0 text-xs text-gray-200">
              {file.name}
            </div>

            {/* File remove button */}
            <button
              className="p-1 hover:bg-red-500/20 rounded"
              onClick={() => onRemoveFile(file.id)}
            >
              <X size={16} className="text-gray-400 hover:text-red-400" />
            </button>
          </div>
        ))}
      </div>
    );
  }

  // HTML for the sidebar file display
  return (
    <div
      className="p-3 border-b border-gray-800/30"
      onDrop={handleDrop}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
    >
      {/* If there are no files, render the empty state */}
      {/* Otherwise, render the file list */}
      {files.length === 0 ? renderEmptyState() : renderFileList()}
    </div>
  );
}
