import { useRef, useState } from "react";
import { ExcelFile, Chat } from "@/app/Interfaces";

const ACCEPTED_FILE_EXTENSIONS = ["xlsx", "xls", "csv"];

interface SidebarProperties {
  onSettingsClick?: () => void;
  onFilesChange: (files: ExcelFile[]) => void;
  onChatSelect?: (chatId: string) => void;
  onNewChat?: () => void;
  files: ExcelFile[];
  chats: Chat[];
  activeChat?: string;
}

function isAcceptedFileType(extension: string): boolean {
  return ACCEPTED_FILE_EXTENSIONS.includes(extension.toLowerCase() as any);
}

function getAcceptAttribute(): string {
  return [...ACCEPTED_FILE_EXTENSIONS].map((ext) => `.${ext}`).join(",");
}

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

  function handleFileSelect(e: React.ChangeEvent<HTMLInputElement>): void {
    const selectedFiles = Array.from(e.target.files || []).filter((file) =>
      isAcceptedFileType(getFileExtension(file.name)),
    );
    addFiles(selectedFiles);
  }

  function handleDrop(e: React.DragEvent): void {
    e.preventDefault();

    const droppedFiles = Array.from(e.dataTransfer.files).filter((file) =>
      isAcceptedFileType(getFileExtension(file.name)),
    );
    addFiles(droppedFiles);
  }

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

  function removeFile(id: string): void {
    const updatedFiles = files.filter((f) => f.id !== id);
    const reindexedFiles = updatedFiles.map((file, idx) => ({
      ...file,
      index: idx + 1,
    }));
    onFilesChange(reindexedFiles);
  }

  function handleDragOver(e: React.DragEvent): void {
    e.preventDefault();
  }

  function handleDragLeave(e: React.DragEvent): void {
    e.preventDefault();
  }

  return (
    <div className="w-72 bg-gray-900/80 backdrop-blur-sm border-r border-gray-800/50 flex flex-col h-full relative">
      {/* Header */}
      <div className="p-4 border-b border-gray-800/50 relative z-10">
        <div className="flex items-center gap-3 px-3 py-2 mb-4">
          <div className="flex-1 min-w-0">
            <div className="text-base font-semibold text-white">Sheet Hero</div>

            <div className="text-xs text-green-400">Spreadsheet AI</div>

            {/* TODO Put logo or smtnh here */}
          </div>
        </div>

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
          className="w-full flex items-center gap-3 px-4 py-3 rounded-lg border border-gray-700/50 text-white group"
        >
          <span className="text-sm font-medium">Upload Files</span>
        </button>
      </div>

      {/* =-=-= Scrollable area for files & chat history =-=-= */}
      <div className="flex-1 overflow-y-auto relative z-10">
        {/* =-=-= Active files box =-=-= */}
        <div
          className="p-3 border-b border-gray-800/30"
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
        >
          <div className="flex items-center justify-between mb-2 px-2">
            <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
              Files
            </h3>

            {files.length > 0 && (
              <span className="text-xs text-gray-500">{files.length}</span>
            )}
          </div>

          {/* If there are no files, display drag & drop instructions */}
          {/* Otherwise, display all the files in the file array */}

          {files.length === 0 ? (
            <div className="text-center px-2 py-4">
              {/* TODO Put some icon here */}
              {/* Display drag & drop instructions */}
              <p className="text-xs text-gray-500">No files uploaded</p>
              <p className="text-xs text-gray-600 mt-1">Drag & drop here</p>
            </div>
          ) : (
            <div className="space-y-1">
              {files.map((file) => (
                <div
                  key={file.id}
                  className="flex items-center gap-2 px-2 py-2 rounded-lg bg-gray-800/50 border border-gray-700/30 hover:border-green-600/30 transition-all group"
                >
                  {/* File display capsule */}
                  <div className="shrink-0 w-5 h-5 rounded bg-green-600/20 flex items-center justify-center">
                    <span className="text-xs font-bold text-green-400">
                      {file.index}
                    </span>
                  </div>

                  {/* File name */}
                  <div className="flex-1 min-w-0">
                    <div
                      className="text-xs text-gray-200 truncate"
                      title={file.name}
                    >
                      {file.name}
                    </div>
                  </div>

                  {/* File remove button */}
                  <button
                    onClick={() => removeFile(file.id)}
                    className="opacity-0 group-hover:opacity-100 transition-opacity p-0.5 hover:bg-red-500/20 rounded"
                    aria-label="Remove file"
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
          <div className="flex items-center justify-between mb-2 px-2">
            <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
              Chats
            </h3>

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
            <div className="text-center px-2 py-4">
              {/* TODO Put some icon here */}
              <p className="text-xs text-gray-500">No chat history</p>
            </div>
          ) : (
            <div className="space-y-1">
              {chats.map((chat) => (
                <button
                  key={chat.id}
                  onClick={() => onChatSelect?.(chat.id)}
                  className={`w-full flex items-start gap-3 px-3 py-3 rounded-lg transition-all text-left group 
                      ${
                        activeChat === chat.id
                          ? "bg-gray-800/80 border border-green-600/30"
                          : "hover:bg-gray-800/80 hover:border hover:border-green-600/20"
                      }
                    `}
                >
                  <div className="flex-1 min-w-0">
                    <div className="text-sm text-gray-200 truncate">
                      {chat.title}
                    </div>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* =-=-= Footer =-=-= */}
      <div className="p-4 border-t border-gray-800/50 relative z-10">
        {/* Settings button */}
        <button
          className="w-full flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-gray-800/80 hover:border hover:border-green-600/20 transition-all text-left group"
          onClick={onSettingsClick}
        >
          {/* TODO Put settings icon here */}

          <span className="text-sm text-gray-200">Settings</span>
        </button>
      </div>
    </div>
  );
}
