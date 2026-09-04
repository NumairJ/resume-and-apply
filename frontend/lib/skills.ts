/**
 * Parsing and grouping helpers for the skills section.
 *
 * Pure functions, kept out of the component so the rules can be tested directly rather
 * than through a rendered form — the dedupe behaviour in particular is easy to get
 * subtly wrong and hard to see in a UI test.
 */

import type { Skill } from "@/types/api";

/**
 * Skill names out of a pasted blob.
 *
 * Splits on commas **and** newlines, because both are how people actually paste: a
 * comma-separated run copied out of a résumé, or one-per-line out of a bulleted list.
 * Duplicates within the paste itself are collapsed, keeping the first spelling.
 */
export function parseSkillNames(text: string): string[] {
  const seen = new Set<string>();
  const names: string[] = [];

  for (const raw of text.split(/[,\n]/)) {
    const name = raw.trim();
    if (!name) continue;

    const key = name.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    names.push(name);
  }

  return names;
}

/**
 * The names not already in the profile, compared case-insensitively.
 *
 * Case-insensitive so that re-pasting an overlapping list tops up rather than creating
 * a second "python" beside "Python" — the guardrails treat skills as a set, and two
 * spellings of one skill is just noise in it.
 */
export function newSkillNames(parsed: string[], existing: Skill[]): string[] {
  const have = new Set(existing.map((skill) => skill.name.trim().toLowerCase()));
  return parsed.filter((name) => !have.has(name.toLowerCase()));
}

/**
 * Categories already in use, in the order they first appear.
 *
 * Feeds the `<datalist>` on both category inputs. Offering what you already typed is
 * what keeps "Languages" and "languages" from becoming two groups, without hard-coding
 * a taxonomy nobody asked for.
 */
export function existingCategories(skills: Skill[]): string[] {
  const seen = new Set<string>();
  const categories: string[] = [];

  for (const skill of skills) {
    const category = skill.category?.trim();
    if (!category || seen.has(category.toLowerCase())) continue;
    seen.add(category.toLowerCase());
    categories.push(category);
  }

  return categories;
}
