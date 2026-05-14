import { ExcelFile } from "@/util/interfaces";
import { FileSpreadsheet } from "lucide-react";
import { SidebarDataCapsule } from "./SidebarDataCapsule";

// Properties needed for the sidebar file display
interface SidebarFileDisplayProperties {
  files: ExcelFile[];
  onRemoveFile: (id: string) => void;
}

export function SidebarFileDisplay({
  files,
  onRemoveFile,
}: SidebarFileDisplayProperties) {
  // Renders an empty state with file upload instructions
  function renderEmptyState() {
    return (
      <div className="text-center p-5">
        <div className="w-10 h-10 rounded-lg bg-(--sh-dark-blue) flex items-center justify-center mx-auto mb-2">
          <FileSpreadsheet size={20} className="text-(--sh-medium-grey)" />
        </div>
        {/* Display file upload instructions */}
        <p className="text-xs text-(--sh-medium-grey)">No files uploaded</p>
        <p className="text-xs text-(--sh-medium-grey)">Upload files to query</p>
      </div>
    );
  }

  // Renders the full file list with all currently active files
  function renderFileList() {
    return (
      <div className="space-y-2">
        {/* List of all files */}
        {files.map((file) => (
          <SidebarDataCapsule
            leftComponent={
              <div className="w-5 h-5 rounded bg-(--sh-green) flex items-center justify-center text-xs font-bold text-(--sh-white)">
                {file.index}
              </div>
            }
            key={file.id}
            text={file.name}
            id={file.id}
            onRemoveCapsule={onRemoveFile}
          />
        ))}
      </div>
    );
  }

  // HTML for the sidebar file display
  return (
    <div className="p-3 border-b border-(--sh-border-grey)">
      {/* If there are no files, render the empty state */}
      {/* Otherwise, render the file list */}
      {files.length === 0 ? renderEmptyState() : renderFileList()}
    </div>
  );
}
