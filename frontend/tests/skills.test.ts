import { describe, expect, it } from "vitest";

import { existingCategories, newSkillNames, parseSkillNames } from "@/lib/skills";
import type { Skill } from "@/types/api";

function skill(name: string, category: string | null = null): Skill {
  return { id: name, name, category, position: 0 };
}

describe("parseSkillNames", () => {
  it("accepts commas, which is how a résumé line pastes", () => {
    expect(parseSkillNames("Python, Go, Rust")).toEqual(["Python", "Go", "Rust"]);
  });

  it("accepts new lines, which is how a bulleted list pastes", () => {
    expect(parseSkillNames("Python\nGo\nRust")).toEqual(["Python", "Go", "Rust"]);
  });

  it("accepts both at once, and tidies the whitespace between them", () => {
    expect(parseSkillNames("  Python , Go\n\n  Rust ,\n")).toEqual([
      "Python",
      "Go",
      "Rust",
    ]);
  });

  it("collapses repeats inside the paste, keeping the first spelling", () => {
    expect(parseSkillNames("Python, python, PYTHON")).toEqual(["Python"]);
  });

  it("is empty for blank or separator-only input", () => {
    expect(parseSkillNames("")).toEqual([]);
    expect(parseSkillNames("  , \n , ")).toEqual([]);
  });
});

describe("newSkillNames", () => {
  it("skips what is already in the profile, whatever the casing", () => {
    const existing = [skill("Python"), skill("Postgres")];
    expect(newSkillNames(["python", "Go", "POSTGRES"], existing)).toEqual(["Go"]);
  });

  it("returns everything when the profile is empty", () => {
    expect(newSkillNames(["Python", "Go"], [])).toEqual(["Python", "Go"]);
  });
});

describe("existingCategories", () => {
  it("lists each category once, in the order it first appears", () => {
    const skills = [
      skill("Python", "Languages"),
      skill("Postgres", "Databases"),
      skill("Go", "Languages"),
    ];
    expect(existingCategories(skills)).toEqual(["Languages", "Databases"]);
  });

  it("ignores skills with no category", () => {
    expect(existingCategories([skill("Python"), skill("Go", "Languages")])).toEqual([
      "Languages",
    ]);
  });

  it("treats differently-cased spellings as one, which is the point of offering them", () => {
    const skills = [skill("Python", "Languages"), skill("Go", "languages")];
    expect(existingCategories(skills)).toEqual(["Languages"]);
  });
});
