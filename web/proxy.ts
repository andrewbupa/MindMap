import { NextResponse, type NextRequest } from "next/server";

const SESSION_COOKIE = "agora_session";

/**
 * Sends visitors without a session cookie straight to sign-in, and passes the
 * requested path on so server components can return people to it afterwards.
 * The cookie is only checked for presence here; the API validates it.
 */
export function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  const path = `${pathname}${search}`;
  if (!request.cookies.has(SESSION_COOKIE)) {
    const login = new URL("/api/auth/login", request.url);
    login.searchParams.set("next", path);
    return NextResponse.redirect(login);
  }
  const headers = new Headers(request.headers);
  headers.set("x-agora-path", path);
  return NextResponse.next({ request: { headers } });
}

export const config = {
  matcher: ["/((?!api/|_next/|signed-out|healthz|icon.svg|favicon.ico|robots.txt).*)"],
};
