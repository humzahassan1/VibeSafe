import { useEffect, useState } from 'react';

export default function Home() {
  const [content, setContent] = useState('');

  useEffect(() => {
    fetch('/api/users?id=1')
      .then(r => r.json())
      .then(data => {
        // XSS: innerHTML with user data
        document.getElementById('user-info').innerHTML = data.bio;
      });
  }, []);

  function handleSearch(e) {
    const query = e.target.value;
    // XSS: document.write
    document.write('<h1>Results for: ' + query + '</h1>');
  }

  return (
    <div>
      <h1>Dashboard</h1>
      <input onChange={handleSearch} placeholder="Search..." />
      <div id="user-info"></div>
    </div>
  );
}
