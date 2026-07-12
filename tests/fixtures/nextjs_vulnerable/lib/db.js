import { createClient } from '@supabase/supabase-js';

// Hardcoded service role key (should be in env only)
const SUPABASE_SERVICE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRlc3QiLCJyb2xlIjoic2VydmljZV9yb2xlIiwiZXhwIjoxNjgxMDg5MjAwfQ.fakesignature";

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL,
  SUPABASE_SERVICE_KEY
);

export function getUser(id) {
  // SQL injection
  return supabase.rpc('raw_query', {
    sql: "SELECT * FROM users WHERE id = " + id
  });
}

export function searchUsers(name) {
  // SQL injection via template literal
  return supabase.rpc('raw_query', {
    sql: `SELECT * FROM users WHERE name LIKE '%${name}%'`
  });
}

export default supabase;
