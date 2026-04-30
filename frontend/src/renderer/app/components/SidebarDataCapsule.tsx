import { X } from "lucide-react";

// Properties needed for the sidebar data capsule
interface SidebarDataCapsuleProperties {
  text: string;
  id: string;
  leftComponent?: React.ReactNode;
  isActive?: boolean;
  onClick?: () => void;
  onRemoveCapsule: (id: string) => void;
}

export function SidebarDataCapsule({
  text,
  id,
  leftComponent,
  isActive,
  onClick,
  onRemoveCapsule,
}: SidebarDataCapsuleProperties) {
  // HTML for the sidebar data capsule
  return (
    <div
      className={`flex items-center gap-2 p-2 rounded-lg bg-(--sh-dark-blue)/80 border transition-all cursor-pointer
        ${isActive ? "border-(--sh-green)" : "border-(--sh-border-grey)"}
      `}
      onClick={onClick}
    >
      {leftComponent}
      <div className="flex-1 min-w-0 text-xs text-(--sh-white)">{text}</div>
      <button
        className="p-1 hover:bg-(--sh-red) rounded"
        onClick={() => {
          onRemoveCapsule(id);
        }}
      >
        <X
          size={16}
          className={`${isActive ? "text-(--sh-green)" : "text-(--sh-medium-grey)"}`}
        />
      </button>
    </div>
  );
}
