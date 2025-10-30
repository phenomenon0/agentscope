"use client";

import Image from "next/image";
import classNames from "classnames";
import type { ChatAttachment } from "@/lib/store/chat-store";

type VisualizationGalleryProps = {
  attachments?: ChatAttachment[];
  className?: string;
};

export function VisualizationGallery({ attachments, className }: VisualizationGalleryProps) {
  if (!attachments || attachments.length === 0) {
    return null;
  }

  const images = attachments.filter((item) => item.type === "image" && (typeof item.src === "string" || typeof item.path === "string"));
  if (images.length === 0) {
    return null;
  }

  return (
    <section className={classNames("grid gap-4 md:grid-cols-2", className)}>
      {images.map((attachment) => {
        const src =
          (attachment.src && attachment.src.length > 0
            ? attachment.src
            : attachment.path
              ? `/api/viz?path=${encodeURIComponent(attachment.path)}`
              : undefined);
        if (!src) {
          return null;
        }
        const altText = attachment.alt && attachment.alt.trim().length > 0 ? attachment.alt : "Visualization";

        return (
          <figure
            key={attachment.id}
            className="overflow-hidden rounded-2xl border border-neutral-200 bg-white shadow-sm"
          >
            <a
              href={src}
              target="_blank"
              rel="noopener noreferrer"
              className="group block"
            >
              <div className="relative h-48 w-full bg-neutral-50">
                <Image
                  src={src}
                  alt={altText}
                  fill
                  sizes="(min-width: 768px) 320px, 100vw"
                  className="object-contain transition-transform duration-200 group-hover:scale-[1.02]"
                  priority={false}
                  unoptimized
                />
              </div>
            </a>
            {attachment.alt && attachment.alt.trim().length > 0 ? (
              <figcaption className="border-t border-neutral-200 px-3 py-2 text-xs text-neutral-500">
                {attachment.alt}
              </figcaption>
            ) : null}
          </figure>
        );
      })}
    </section>
  );
}
