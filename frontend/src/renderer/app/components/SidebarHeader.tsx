import { ReactNode } from "react";

// Properties needed for the sidebar header
interface SidebarHeaderProperties {
  title: string;
  content: ReactNode;
}

export function SidebarHeader({ title, content }: SidebarHeaderProperties) {
  // HTML for the sidebar header
  return (
    <div className="flex items-center justify-between p-3">
      <h3 className="text-xs text-(--sh-medium-grey)">{title}</h3>
      {content}
    </div>
  );
}
