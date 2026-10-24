import { useEffect, useRef, type ReactNode } from "react";
import { X } from "lucide-react";

export function CouncilSetupSurface({
  explain,
  open,
  onClose,
  children,
}: {
  explain: boolean;
  open: boolean;
  onClose: () => void;
  children: ReactNode;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    if (explain || !open) return;
    const previous = document.activeElement as HTMLElement | null;
    const panel = dialog.current;
    panel?.showModal();
    return () => {
      panel?.close();
      previous?.focus();
    };
  }, [explain, open]);

  if (explain) return <div id="council-customize-content">{children}</div>;
  return (
    <dialog
      ref={dialog}
      id="council-customize-content"
      className="council-settings-dialog"
      aria-labelledby="council-settings-title"
      onCancel={onClose}
      onClose={onClose}
    >
      <header>
        <h2 id="council-settings-title">Council settings</h2>
        <button
          type="button"
          className="council-icon"
          aria-label="Close settings"
          onClick={onClose}
        >
          <X size={18} />
        </button>
      </header>
      <div className="council-settings-body">{children}</div>
      <footer>
        <button type="button" onClick={onClose}>
          Done
        </button>
      </footer>
    </dialog>
  );
}
