import { useRef } from "react";
import { ExcelFile, Chat } from "@/util/interfaces";

const ACCEPTED_FILE_EXTENSIONS = ["xlsx", "xls", "csv"] as const;

interface SidebarProperties {
  onSettingsClick?: () => void;
  onFilesChange: (files: ExcelFile[]) => void;
  onChatSelect?: (chatId: string) => void;
  onNewChat?: () => void;
  files: ExcelFile[];
  chats: Chat[];
  activeChat?: string;
}

// Checks if a file type is valid
function isAcceptedFileType(extension: string): boolean {
  return ACCEPTED_FILE_EXTENSIONS.some(
    (ext) => ext === extension.toLowerCase(),
  );
}

// Returns all file extensions, used for file dialog
function getAcceptAttribute(): string {
  return [...ACCEPTED_FILE_EXTENSIONS].map((ext) => `.${ext}`).join(",");
}

// Gets the extension name of a file
function getFileExtension(fileName: string): string {
  const parts = fileName.split(".");

  if (parts.length > 1) return parts.pop()!;
  else return "";
}

export function Sidebar({
  onSettingsClick,
  onFilesChange,
  onChatSelect,
  onNewChat,
  files,
  chats,
  activeChat,
}: SidebarProperties) {
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Handles when files are selected from the file dialog
  function handleFileSelect(event: React.ChangeEvent<HTMLInputElement>): void {
    const selectedFiles = Array.from(event.target.files || []).filter((file) =>
      isAcceptedFileType(getFileExtension(file.name)),
    );

    if (selectedFiles.length === 0) return;

    addFiles(selectedFiles);

    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  // Adds a file when dropped into the drap & drop container
  function handleDrop(event: React.DragEvent): void {
    event.preventDefault();

    const droppedFiles = Array.from(event.dataTransfer.files).filter((file) =>
      isAcceptedFileType(getFileExtension(file.name)),
    );
    addFiles(droppedFiles);
  }

  // Adds a file to the file list
  function addFiles(newFiles: File[]): void {
    const currentMaxIndex =
      files.length > 0 ? Math.max(...files.map((f) => f.index)) : 0;
    const excelFiles: ExcelFile[] = newFiles.map((file, idx) => ({
      id: `${Date.now()} - ${idx}`,
      name: file.name,
      index: currentMaxIndex + idx + 1,
      file,
    }));
    onFilesChange([...files, ...excelFiles]);
  }

  // Removes a file from the file list
  function removeFile(id: string): void {
    const updatedFiles = files.filter((f) => f.id !== id);
    const reindexedFiles = updatedFiles.map((file, idx) => ({
      ...file,
      index: idx + 1,
    }));
    onFilesChange(reindexedFiles);
  }

  // Makes the drag & drop functionality work properly
  function handleDragOver(event: React.DragEvent): void {
    event.preventDefault();
  }

  // Makes the drag & drop functionality work properly
  function handleDragLeave(event: React.DragEvent): void {
    event.preventDefault();
  }

  // HTML for the sidebar
  return (
    <div className="w-75 bg-gray-900/80 border-r border-gray-800/50 flex flex-col h-full">
      {/* =-=-= Header =-=-=*/}
      <div className="p-4 border-b border-gray-800/50">
        <div className="flex items-center p-3">
          <div className="flex-1 min-w-0">
            <div className="text-base font-semibold text-white">Sheet Hero</div>
            <div className="text-xs text-green-400">Spreadsheet AI</div>

            {/* TODO Put logo or smtnh here */}
          </div>
        </div>

        {/* File dialog for selecting files */}
        <input
          className="hidden"
          type="file"
          multiple
          accept={getAcceptAttribute()}
          onChange={handleFileSelect}
          ref={fileInputRef}
        />

        <button
          onClick={() => fileInputRef.current?.click()}
          className="flex w-full items-center bg-gray-900 p-4 rounded-lg border border-gray-700/50 text-white hover:border-green-600/30 hover:bg-gray-800/80 transition-all"
        >
          <span className="text-sm font-medium">Upload Files</span>
        </button>
      </div>

      {/* =-=-= Scrollable area for files & chat history =-=-= */}
      <div className="flex-1 overflow-y-auto relative">
        {/* =-=-= Active files box =-=-= */}
        <div
          className="p-3 border-b border-gray-800/30"
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
        >
          <div className="flex items-center justify-between p-1">
            <h3 className="text-xs font-semibold text-gray-400 py-1">FILES</h3>

            {files.length > 0 && (
              <span className="text-xs text-gray-500">{files.length}</span>
            )}
          </div>

          {/* If there are no files, display drag & drop instructions */}
          {/* Otherwise, display all the files in the file array */}

          {files.length === 0 ? (
            <div className="text-center p-5">
              {/* TODO Put some icon here */}
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
                    <span className="text-xs font-bold text-green-400">
                      {file.index}
                    </span>
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
                    onClick={() => removeFile(file.id)}
                  >
                    X {/* TODO <-- Make this an icon */}
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* =-=-= Chat history box =-=-= */}
        <div className="p-3">
          {/* Chats title */}
          <div className="flex items-center justify-between p-1">
            <h3 className="text-xs font-semibold text-gray-400 py-1">CHATS</h3>

            {/* Create new chat button */}
            <button
              onClick={onNewChat}
              className="text-xs text-gray-500 hover:text-green-400 transition-colors"
            >
              + New
            </button>
          </div>

          {/* If there are no chats, display no chat history */}
          {/* Otherwise, display all the chats in the chat array */}
          {chats.length === 0 ? (
            <div className="text-center p-3">
              {/* TODO Put some icon here */}
              <p className="text-xs text-gray-500">No chat history</p>
            </div>
          ) : (
            <div className="space-y-1">
              {chats.map((chat) => (
                <button
                  key={chat.id}
                  onClick={() => onChatSelect?.(chat.id)}
                  className={`w-full flex p-4 rounded-lg text-left 
                      ${
                        activeChat === chat.id
                          ? "bg-gray-800/80 border border-green-600/30"
                          : "hover:bg-gray-800/20"
                      }
                    `}
                >
                  <div className="flex-1">
                    <div className="text-sm text-gray-200">{chat.title}</div>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* =-=-= Footer =-=-= */}
      <div className="p-4 border-t border-gray-800/50">
        {/* Settings button */}
        <button
          className="w-full flex items-center p-4 rounded-lg bg-gray-900 hover:bg-gray-800/80 border border-gray-700/50 hover:border-green-600/20 transition-all"
          onClick={onSettingsClick}
        >
          {/* TODO Put settings icon here */}

          <span className="text-sm text-gray-200">Settings</span>
        </button>
      </div>
    </div>
  );
}
