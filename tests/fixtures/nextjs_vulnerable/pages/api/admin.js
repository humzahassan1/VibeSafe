export default function handler(req, res) {
  // Default credentials
  const ADMIN_USER = "admin";
  const ADMIN_PASS = "admin123";

  const { username, password } = req.body;

  if (username === ADMIN_USER && password === ADMIN_PASS) {
    // eval for dynamic code execution
    const action = req.query.action;
    const result = eval(action);
    res.json({ result });
  }

  res.status(401).json({ error: "Unauthorized" });
}
