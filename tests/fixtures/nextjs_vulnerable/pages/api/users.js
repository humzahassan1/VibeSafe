import { createClient } from '@supabase/supabase-js';

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL,
  "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRlc3QiLCJyb2xlIjoic2VydmljZV9yb2xlIiwiZXhwIjoxNjgxMDg5MjAwfQ.fakesignature"
);

export default async function handler(req, res) {
  const { id } = req.query;

  // SQL injection via string concatenation
  const { data } = await supabase.rpc('get_user', {
    query: `SELECT * FROM users WHERE id = ${id}`
  });

  // Sensitive data logging
  console.log("User auth token:", req.headers.authorization);
  console.log("Full request body:", JSON.stringify(req.body));

  // No authentication check
  if (req.method === 'DELETE') {
    await supabase.from('users').delete().eq('id', id);
    return res.json({ deleted: true });
  }

  res.json(data);
}
