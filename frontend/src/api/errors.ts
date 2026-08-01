/**
 * Turning an API error into something safe to render.
 *
 * FastAPI reports validation failures as a *list of objects*
 * (`[{loc, msg, type}, ...]`), not a string. Passing that straight to a MUI
 * label or `<Typography>` throws "Objects are not valid as a React child",
 * which unmounts the tree and leaves a blank page — so a recoverable 422 turns
 * into a dead screen. Everything that displays a server error should go through
 * here.
 */
export function readErrorMessage(err: unknown, fallback: string): string {
  const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data
    ?.detail;

  // The common case: HTTPException(detail="...") from our own routers.
  if (typeof detail === 'string') return detail;

  // Pydantic validation errors. Only the first is shown; the rest are almost
  // always the same mistake repeated across fields.
  if (Array.isArray(detail)) {
    const first = detail[0] as { msg?: unknown; loc?: unknown } | undefined;
    if (typeof first?.msg === 'string') {
      const field = Array.isArray(first.loc) ? first.loc[first.loc.length - 1] : null;
      // "Value error, " is Pydantic's own prefix and means nothing to a user.
      const message = first.msg.replace(/^Value error, /, '');
      return typeof field === 'string' && field !== 'body'
        ? `${field}: ${message}`
        : message;
    }
  }

  return fallback;
}
