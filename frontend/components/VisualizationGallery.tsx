"use client";

import { useState, useRef, useEffect } from "react";
import Image from "next/image";
import classNames from "classnames";
import type { ChatAttachment } from "@/lib/store/chat-store";

type VisualizationGalleryProps = {
  attachments?: ChatAttachment[];
  className?: string;
  onAllImagesLoaded?: () => void;
};

export function VisualizationGallery({ attachments, className, onAllImagesLoaded }: VisualizationGalleryProps) {
  const loadedCountRef = useRef(0);
  const totalCountRef = useRef(0);
  const callbackFiredRef = useRef(false);

  if (!attachments || attachments.length === 0) {
    return null;
  }

  const images = attachments.filter((item) => item.type === "image" && (typeof item.src === "string" || typeof item.path === "string"));
  if (images.length === 0) {
    return null;
  }

  totalCountRef.current = images.length;
  loadedCountRef.current = 0;
  callbackFiredRef.current = false;

  const handleImageLoad = () => {
    loadedCountRef.current += 1;
    if (loadedCountRef.current === totalCountRef.current && !callbackFiredRef.current) {
      callbackFiredRef.current = true;
      // Wait a bit for layout to fully settle
      setTimeout(() => {
        onAllImagesLoaded?.();
      }, 100);
    }
  };

  const gridClass = images.length === 1
    ? "grid gap-4 grid-cols-1"
    : "grid gap-4 md:grid-cols-1 lg:grid-cols-2";

  return (
    <section className={classNames(gridClass, className)}>
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

        return <VisualizationImage key={attachment.id} src={src} alt={altText} onLoad={handleImageLoad} />;
      })}
    </section>
  );
}

function VisualizationImage({ src, alt, onLoad }: { src: string; alt: string; onLoad?: () => void }) {
  const [isLoading, setIsLoading] = useState(true);

  const handleLoad = () => {
    setIsLoading(false);
    onLoad?.();
  };

  return (
    <figure className="overflow-hidden rounded-2xl border border-neutral-200 bg-white shadow-sm">
      <a href={src} target="_blank" rel="noopener noreferrer" className="group block">
        <div className="relative h-96 md:h-[500px] w-full bg-neutral-50">
          {isLoading && (
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="h-8 w-8 animate-spin rounded-full border-4 border-neutral-300 border-t-neutral-600" />
            </div>
          )}
          <Image
            src={src}
            alt={alt}
            fill
            sizes="(min-width: 1024px) 50vw, 100vw"
            className={classNames(
              "object-contain transition-all duration-300",
              isLoading ? "opacity-0" : "opacity-100 group-hover:scale-[1.02]"
            )}
            onLoad={handleLoad}
            priority={false}
            unoptimized
          />
        </div>
      </a>
      {alt && alt.trim().length > 0 ? (
        <figcaption className="border-t border-neutral-200 px-3 py-2 text-xs text-neutral-500">
          {alt}
        </figcaption>
      ) : null}
    </figure>
  );
}
