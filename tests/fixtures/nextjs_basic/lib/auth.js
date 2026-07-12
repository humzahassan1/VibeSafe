export function getSession(req) {
  return req.cookies.session || null;
}
