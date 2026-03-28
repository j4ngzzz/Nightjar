import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Merges Tailwind CSS class names, resolving conflicts correctly.
 * Uses clsx for conditional class composition + tailwind-merge for conflict resolution.
 *
 * @example
 * cn("px-4 py-2", condition && "bg-amber-500", "px-6") // px-6 wins over px-4
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
