"use client";

import { useEffect, useRef, type ReactNode } from "react";

import { Button } from "@/components/ui";

/**
 * Built on the native `<dialog>` element.
 *
 * `showModal()` gives focus trapping, Esc-to-close, inertness of the page behind, and
 * the top-layer stacking that otherwise needs a z-index fight — all things a
 * hand-rolled modal gets subtly wrong, and none of them worth a dependency here.
 */
export function Modal({
  open,
  onClose,
  title,
  children,
  footer,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  footer?: ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    // Guarded: jsdom does not implement showModal, and the test setup stubs it.
    if (open && !dialog.open) dialog.showModal?.();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      // Clicking the backdrop closes. The backdrop is the dialog element itself, so
      // this checks the click landed outside the inner panel rather than on it.
      onClick={(event) => {
        if (event.target === ref.current) onClose();
      }}
      className="m-auto w-full max-w-lg rounded-[2px] border border-ink bg-paper p-0 backdrop:bg-ink/20"
    >
      <div className="p-6">
        <h2 className="display mb-4 text-lg font-semibold">{title}</h2>
        {children}
        <div className="mt-6 flex justify-end gap-2">
          {footer ?? (
            <Button type="button" onClick={onClose}>
              Close
            </Button>
          )}
        </div>
      </div>
    </dialog>
  );
}

export function ConfirmModal({
  open,
  onClose,
  onConfirm,
  title,
  children,
  confirmLabel = "Delete",
}: {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title: string;
  children: ReactNode;
  confirmLabel?: string;
}) {
  return (
    <Modal
      open={open}
      onClose={onClose}
      title={title}
      footer={
        <>
          <Button type="button" variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button type="button" variant="danger" onClick={onConfirm}>
            {confirmLabel}
          </Button>
        </>
      }
    >
      <p className="text-sm text-muted">{children}</p>
    </Modal>
  );
}
