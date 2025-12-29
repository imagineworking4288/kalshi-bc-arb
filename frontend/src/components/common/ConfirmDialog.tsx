import { AlertTriangle } from 'lucide-react';
import { Modal } from './Modal';
import { Button } from './Button';

interface ConfirmDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title: string;
  message: string;
  confirmText?: string;
  cancelText?: string;
  variant?: 'danger' | 'warning';
  loading?: boolean;
}

export function ConfirmDialog({
  isOpen,
  onClose,
  onConfirm,
  title,
  message,
  confirmText = 'Confirm',
  cancelText = 'Cancel',
  variant = 'danger',
  loading = false,
}: ConfirmDialogProps) {
  return (
    <Modal isOpen={isOpen} onClose={onClose} size="sm">
      <div className="text-center">
        <div
          className={`mx-auto flex h-12 w-12 items-center justify-center rounded-full ${
            variant === 'danger' ? 'bg-red-900/50' : 'bg-yellow-900/50'
          }`}
        >
          <AlertTriangle
            className={`h-6 w-6 ${
              variant === 'danger' ? 'text-red-400' : 'text-yellow-400'
            }`}
          />
        </div>

        <h3 className="mt-4 text-lg font-semibold text-white">{title}</h3>
        <p className="mt-2 text-sm text-gray-400">{message}</p>

        <div className="mt-6 flex justify-center gap-3">
          <Button variant="secondary" onClick={onClose} disabled={loading}>
            {cancelText}
          </Button>
          <Button
            variant={variant === 'danger' ? 'danger' : 'primary'}
            onClick={onConfirm}
            loading={loading}
          >
            {confirmText}
          </Button>
        </div>
      </div>
    </Modal>
  );
}
