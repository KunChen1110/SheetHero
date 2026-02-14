import { ExcelFile } from "@/util/interfaces";
import { FileSpreadsheet } from "lucide-react";

interface DragAndDropProperties {
  files: ExcelFile[];
  onAddFiles: (files: File[]) => void;
  onRemoveFile: (id: string) => void;
}

export function FileDisplay({
  files,
  onAddFiles,
  onRemoveFile,
}: DragAndDropProperties) {
  // Handles when a file was dropped in to the drag and drop container
  function handleDrop(event: React.DragEvent): void {
    event.preventDefault();
    const droppedFiles = Array.from(event.dataTransfer.files);
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

  // HTML for the file display
  return (
    <div
      className="p-3 border-b border-gray-800/30"
      onDrop={handleDrop}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
    >
      <div className="flex items-center justify-between p-1">
        <h3 className="text-xs font-semibold text-gray-400 py-1">FILES</h3>

        {files.length > 0 && (
          <div className="text-xs text-gray-500">{files.length}</div>
        )}
      </div>

      {/* If there are no files, display drag & drop instructions */}
      {/* Otherwise, display all the files in the file array */}

      {files.length === 0 ? (
        <div className="text-center p-5">
          <div className="w-10 h-10 rounded-lg bg-gray-800/50 flex items-center justify-center mx-auto mb-2">
            <FileSpreadsheet size={20} className="text-gray-600" />
          </div>
          {/* Display drag & drop instructions */}
          <p className="text-xs text-gray-500">No files uploaded</p>
          <p className="text-xs text-gray-600">Drag & drop here</p>
        </div>
      ) : (
        <div className="space-y-1">
          {files.map((file) => (
            <div
              key={file.id}
              className="flex items-center gap-2 p-2 rounded-lg bg-gray-800/80 border border-gray-700/30 hover:border-green-600/30"
            >
              {/* =-=-= File display capsule =-=-= */}
              <div className="w-5 h-5 rounded bg-green-600/20 flex items-center justify-center">
                <div className="text-xs font-bold text-green-400">
                  {file.index}
                </div>
              </div>

              {/* File name */}
              <div className="flex-1 min-w-0">
                <div className="text-xs text-gray-200" title={file.name}>
                  {file.name}
                </div>
              </div>

              {/* File remove button */}
              <button
                className="p-1 hover:bg-red-500/20 rounded"
                onClick={() => onRemoveFile(file.id)}
              >
                X {/* TODO <-- Make this an icon */}
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
