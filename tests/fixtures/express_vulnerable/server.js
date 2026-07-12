const express = require('express');
const cors = require('cors');
const app = express();

// SEC-039: Permissive CORS
app.use(cors());

// SEC-001: Hardcoded API key
const apiKey = "prod_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5";

// SEC-001: AWS key
const AWS_KEY = "AKIAIOSFODNN7EXAMPLE";

// SEC-004: Hardcoded database connection string
const DB_URL = "postgres://admin:secretpassword@prod-db.internal:5432/mydb";

// SEC-018: Default credentials
const adminUser = "admin";
const adminPassword = "password123";

// SEC-046: Logging sensitive data
console.log("User password is:", password);

// SEC-020: SQL injection via concatenation
function getUser(id) {
  return db.query("SELECT * FROM users WHERE id = " + id);
}

// SEC-022: eval usage
function parseInput(data) {
  return eval(data);
}

// SEC-022: innerHTML
function renderContent(html) {
  document.getElementById('content').innerHTML = html;
}

app.listen(3000);
