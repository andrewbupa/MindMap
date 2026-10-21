import type { MeOut, Role } from "./api";

export const ROLE_LABELS: Record<Role, string> = {
  author: "Author",
  reviewer: "Reviewer",
  compliance: "Compliance",
  admin: "Admin",
};

/** Admins pass every role check, as they do in the API. */
export function hasRole(user: MeOut, ...roles: Role[]): boolean {
  return user.roles.includes("admin") || roles.some((role) => user.roles.includes(role));
}

export function loginUrl(next: string): string {
  return `/api/auth/login?next=${encodeURIComponent(next)}`;
}
