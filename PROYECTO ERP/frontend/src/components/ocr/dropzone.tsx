import * as React from "react";
import { FileImage, Upload, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

interface DropzoneProps {
  onFile: (file: File) => void;
  selectedFile: File | null;
  onClear: () => void;
  disabled?: boolean;
}

const ACCEPT = "image/jpeg,image/png,image/webp,application/pdf";

export function Dropzone({
  onFile,
  selectedFile,
  onClear,
  disabled,
}: DropzoneProps) {
  const inputRef = React.useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = React.useState(false);
  const [previewUrl, setPreviewUrl] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (!selectedFile) {
      setPreviewUrl(null);
      return;
    }
    if (selectedFile.type.startsWith("image/")) {
      const url = URL.createObjectURL(selectedFile);
      setPreviewUrl(url);
      return () => URL.revokeObjectURL(url);
    }
    setPreviewUrl(null);
  }, [selectedFile]);

  const handlePick = (file: File | undefined) => {
    if (!file) return;
    onFile(file);
  };

  const onDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragOver(false);
    if (disabled) return;
    handlePick(e.dataTransfer.files?.[0]);
  };

  if (selectedFile) {
    return (
      <div className="rounded-xl border border-border bg-card shadow-apple p-5 transition-all duration-200 ease-apple">
        <div className="flex items-start gap-4">
          {previewUrl ? (
            <img
              src={previewUrl}
              alt="preview"
              className="h-24 w-24 rounded-[10px] object-cover shadow-apple"
            />
          ) : (
            <div className="h-24 w-24 rounded-[10px] bg-muted flex items-center justify-center">
              <FileImage
                className="h-8 w-8 text-muted-foreground"
                strokeWidth={1.5}
              />
            </div>
          )}
          <div className="flex-1 min-w-0">
            <div className="text-sm font-medium truncate">
              {selectedFile.name}
            </div>
            <div className="text-xs text-muted-foreground mt-0.5">
              {(selectedFile.size / 1024).toFixed(1)} KB ·{" "}
              {selectedFile.type || "archivo"}
            </div>
          </div>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            onClick={onClear}
            disabled={disabled}
            aria-label="Quitar archivo"
          >
            <X className="h-4 w-4" strokeWidth={1.5} />
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        if (!disabled) setDragOver(true);
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={onDrop}
      onClick={() => !disabled && inputRef.current?.click()}
      className={cn(
        "relative cursor-pointer rounded-xl border-2 border-dashed transition-all duration-200 ease-apple p-12 text-center",
        dragOver
          ? "border-primary bg-primary/5 scale-[1.01]"
          : "border-border hover:border-primary/40 hover:bg-muted/30",
        disabled && "opacity-50 pointer-events-none",
      )}
    >
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPT}
        className="hidden"
        onChange={(e) => handlePick(e.target.files?.[0])}
      />
      <div className="flex flex-col items-center gap-3">
        <div className="h-14 w-14 rounded-full bg-primary/10 flex items-center justify-center">
          <Upload className="h-6 w-6 text-primary" strokeWidth={1.5} />
        </div>
        <div>
          <div className="text-[15px] font-medium">
            Arrastrá una foto del comprobante o hacé click
          </div>
          <div className="text-xs text-muted-foreground mt-1">
            JPG, PNG, WEBP o PDF — máx 10MB
          </div>
        </div>
      </div>
    </div>
  );
}
