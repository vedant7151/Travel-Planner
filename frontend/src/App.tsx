import React, { useState } from 'react';

export default function App() {
  const [destination, setDestination] = useState('');

  const handlePlan = (e) => {
    e.preventDefault();
    fetch('http://localhost:8000/api/v1/trips/plan', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ destination })
    }).then(res => res.json()).then(console.log);
  };

  return (
    <div>
      <h1>Travel Planner</h1>
      <form onSubmit={handlePlan}>
        <input 
          type="text" 
          value={destination} 
          onChange={e => setDestination(e.target.value)} 
          placeholder="Destination" 
        />
        <button type="submit">Plan Trip</button>
      </form>
    </div>
  );
}
