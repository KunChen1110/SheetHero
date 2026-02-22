import { Role } from "@/util/interfaces";
import { FileSpreadsheet, User } from "lucide-react";

// Properties needed for the app message
interface AppMessageProperties {
  role: Role;
  content: string;
}

export function AppMessage({ role, content }: AppMessageProperties) {
  // Check if the role of the message is the user
  const isUser = role === Role.USER;

  // HTML for the app message
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`flex ${isUser ? "flex-row-reverse" : "flex-row"} gap-4 p-4 max-w-xl rounded-2xl border border-(--sh-border-grey)
      `}
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
          <div className="text-md text-(--sh-white) py-1">{content}</div>
        </div>
      </div>
    </div>
  );
}
