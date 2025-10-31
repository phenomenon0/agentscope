import { cn } from "@/lib/utils";
import type { ComponentPropsWithoutRef } from "react";

type BubbleBackgroundProps = {
  interactive?: boolean;
} & ComponentPropsWithoutRef<"div">;

export function BubbleBackground({
  interactive = false,
  className,
  children,
  ...props
}: BubbleBackgroundProps) {
  return (
    <div
      {...props}
      className={cn(
        "relative overflow-hidden bg-[#eef1f7] transition",
        interactive ? "pointer-events-auto" : "pointer-events-none",
        className,
      )}
    >
      <div className="absolute inset-0 bg-gradient-to-br from-[#f8fafc] via-[#eef2ff] to-[#e4e7f5]" />
      <div className="absolute -top-40 left-10 h-96 w-96 rounded-full bg-[radial-gradient(circle_at_top,_rgba(255,172,120,0.3),_transparent_70%)] blur-3xl" />
      <div className="absolute -bottom-32 right-0 h-[28rem] w-[28rem] rounded-full bg-[radial-gradient(circle_at_bottom,_rgba(110,154,245,0.38),_transparent_70%)] blur-3xl" />
      <div className="absolute -top-24 right-20 h-60 w-60 rounded-full bg-[radial-gradient(circle,_rgba(164,237,231,0.35),_transparent_70%)] blur-2xl" />
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,_rgba(255,255,255,0.65),_transparent_65%)]" />
      <div className="absolute inset-0 bg-[linear-gradient(120deg,rgba(255,255,255,0.3)_0%,rgba(255,255,255,0)_45%,rgba(255,255,255,0)_55%,rgba(255,255,255,0.35)_100%)] mix-blend-screen opacity-70" />

      <div className="relative">{children}</div>
    </div>
  );
}

type BubbleBackgroundDemoProps = {
  interactive: boolean;
};

export const BubbleBackgroundDemo = ({ interactive }: BubbleBackgroundDemoProps) => {
  return (
    <BubbleBackground
      interactive={interactive}
      className="absolute inset-0 flex items-center justify-center rounded-xl"
    />
  );
};
