export function requireEnv(name: string, value: string | undefined): string {
  if (!value) {
    throw new Error(
      `Missing environment variable ${name}. Copy apps/web/.env.example to apps/web/.env.local.`,
    );
  }
  return value;
}

// NEXT_PUBLIC_* values must be referenced literally so Next.js can inline them.
export const API_URL = requireEnv("NEXT_PUBLIC_API_URL", process.env.NEXT_PUBLIC_API_URL);
// Generated paths already start with /api/v1, so the client only needs the origin.
export const API_ORIGIN = new URL(API_URL).origin;
