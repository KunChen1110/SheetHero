import { useState } from "react";
import { Role, UiThought } from "@/util/interfaces";
import { ChevronDown, ChevronRight, FileSpreadsheet, FolderOpen, User } from "lucide-react";

// Properties needed for the app message
interface AppMessageProperties {
  role: Role;
  content: string;
  hasOutputFile?: boolean;
  outputPath?: string | null;
  detailsMarkdown?: string;
  uiThoughts?: UiThought[];
}

// Parses a markdown table string into headers and rows
function parseMarkdownTable(markdown: string): { headers: string[]; rows: string[][] } | null {
  const lines = markdown.split("\n").map((l) => l.trim()).filter(Boolean);
  const tableLines = lines.filter((l) => l.startsWith("|"));
  if (tableLines.length < 3) return null;

  const parseRow = (line: string) =>
    line.split("|").slice(1, -1).map((cell) => cell.trim());

  const headers = parseRow(tableLines[0]);
  // tableLines[1] is the separator row (| --- | --- |), skip it
  const rows = tableLines.slice(2).map(parseRow);
  return { headers, rows };
}

// Extracts label text and table from details_markdown
function parseContextPreview(markdown: string): { label: string; table: ReturnType<typeof parseMarkdownTable> } | null {
  if (!markdown.trim()) return null;
  const lines = markdown.split("\n");
  const labelLines: string[] = [];
  for (const line of lines) {
    if (line.trim().startsWith("|")) break;
    if (line.trim()) labelLines.push(line.trim());
  }
  const label = labelLines.join(" ");
  const table = parseMarkdownTable(markdown);
  return { label, table };
}

// Renders message content — plain text, or a markdown table when detected
function MessageContent({ content }: { content: string }) {
  const parsed = parseContextPreview(content);
  if (parsed && parsed.table) {
    return (
      <div className="py-1">
        {parsed.label && (
          <p className="text-sm text-(--sh-white) mb-2">{parsed.label}</p>
        )}
        <div className="overflow-x-auto rounded-lg border border-(--sh-border-grey)">
          <table className="text-xs w-full border-collapse">
            <thead>
              <tr className="bg-(--sh-green-highlight)">
                {parsed.table.headers.map((h, i) => (
                  <th key={i} className="px-3 py-2 text-left text-(--sh-white) font-semibold whitespace-nowrap">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {parsed.table.rows.map((row, ri) => (
                <tr key={ri} className={ri % 2 === 0 ? "bg-(--sh-dark-blue)" : "bg-(--sh-border-grey)/20"}>
                  {row.map((cell, ci) => (
                    <td key={ci} className="px-3 py-1.5 text-(--sh-white) whitespace-nowrap border-t border-(--sh-border-grey)">
                      {cell}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  }
  return <div className="text-md text-(--sh-white) py-1">{content}</div>;
}

const STAGE_LABELS: Record<string, string> = {
  understanding: "Understanding",
  diagnosing: "Diagnosing",
  cleaning: "Cleaning",
  executing: "Executing",
  validation: "Validating",
  qa: "Clarifying",
  final_response: "Responding",
};

const STATUS_COLORS: Record<string, string> = {
  running: "bg-yellow-500",
  done: "bg-(--sh-green-highlight)",
  skipped: "text-(--sh-grey)",
  error: "bg-red-500",
};

function ThoughtsLog({ thoughts }: { thoughts: UiThought[] }) {
  const [open, setOpen] = useState(false);

  // Deduplicate: keep the last entry per stage
  const byStage = new Map<string, UiThought>();
  for (const t of thoughts) {
    byStage.set(t.stage, t);
  }
  const steps = Array.from(byStage.values());

  return (
    <div className="mt-3">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1 text-xs text-(--sh-grey) hover:text-(--sh-white) transition-colors"
      >
        {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        Processing steps ({steps.length})
      </button>

      {open && (
        <div className="mt-2 space-y-1">
          {steps.map((t, i) => {
            const label = STAGE_LABELS[t.stage] ?? t.stage;
            const dotColor = STATUS_COLORS[t.status] ?? "bg-(--sh-grey)";
            return (
              <div key={i} className="flex items-center gap-2 text-xs text-(--sh-grey)">
                <span className={`w-2 h-2 rounded-full shrink-0 ${dotColor}`} />
                <span className="text-(--sh-white)">{label}</span>
                <span className="opacity-60">{t.status}</span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

export function AppMessage({ role, content, hasOutputFile, outputPath, detailsMarkdown, uiThoughts }: AppMessageProperties) {
  const isUser = role === Role.USER;
  const preview = !isUser && detailsMarkdown ? parseContextPreview(detailsMarkdown) : null;
  const hasThoughts = !isUser && uiThoughts && uiThoughts.length > 0;

  function handleOpenFolder(): void {
    if (outputPath) {
      window.electronAPI.openPath(outputPath);
    }
  }

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`flex ${isUser ? "flex-row-reverse" : "flex-row"} gap-4 p-4 max-w-xl rounded-2xl border border-(--sh-border-grey)`}
      >
        <div className="shrink-0">
          <div
            className={`w-8 h-8 rounded-full flex items-center justify-center
              ${isUser ? "bg-(--sh-blue) text-(--sh-white)" : "bg-(--sh-green-highlight) text-(--sh-white)"}
            `}
          >
            {isUser ? <User size={22} /> : <FileSpreadsheet size={22} />}
          </div>
        </div>

        {/* Message contents */}
        <div className="flex-1 min-w-0">
          <MessageContent content={content} />

          {/* Context preview table */}
          {preview && (
            <div className="mt-3">
              {preview.label && (
                <p className="text-xs text-(--sh-grey) mb-2">{preview.label}</p>
              )}
              {preview.table && (
                <div className="overflow-x-auto rounded-lg border border-(--sh-border-grey)">
                  <table className="text-xs w-full border-collapse">
                    <thead>
                      <tr className="bg-(--sh-green-highlight)">
                        {preview.table.headers.map((h, i) => (
                          <th key={i} className="px-3 py-2 text-left text-(--sh-white) font-semibold whitespace-nowrap">
                            {h}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {preview.table.rows.map((row, ri) => (
                        <tr key={ri} className={ri % 2 === 0 ? "bg-(--sh-dark-blue)" : "bg-(--sh-border-grey)/20"}>
                          {row.map((cell, ci) => (
                            <td key={ci} className="px-3 py-1.5 text-(--sh-white) whitespace-nowrap border-t border-(--sh-border-grey)">
                              {cell}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {/* Processing steps log */}
          {hasThoughts && <ThoughtsLog thoughts={uiThoughts!} />}
        </div>

        {/* Output file button */}
        {!isUser && hasOutputFile && outputPath && (
          <button
            onClick={handleOpenFolder}
            className="mt-2 flex items-center gap-2 px-3 py-1.5 text-xs font-medium rounded-lg bg-(--sh-green-highlight) text-(--sh-white) hover:bg-(--sh-green) transition-colors"
          >
            <FolderOpen size={14} />
            Open Output Folder
          </button>
        )}
      </div>
    </div>
  );
}
