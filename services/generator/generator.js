const https = require('https');

// Simulates soil sensor readings — ties to your DAXSoil research
const SENSORS    = ['sensor-karnataka-01', 'sensor-maharashtra-01',
                    'sensor-manipal-01',   'sensor-bangalore-01'];
const EVENT_TYPES = ['nitrogen_reading', 'phosphorus_reading',
                     'potassium_reading', 'moisture_reading',
                     'temperature_reading'];

function generateEvent() {
  const sensor    = SENSORS[Math.floor(Math.random() * SENSORS.length)];
  const eventType = EVENT_TYPES[Math.floor(Math.random() * EVENT_TYPES.length)];

  // Realistic sensor value ranges
  const ranges = {
    nitrogen_reading:    { min: 10,  max: 280 },
    phosphorus_reading:  { min: 4,   max: 120 },
    potassium_reading:   { min: 50,  max: 400 },
    moisture_reading:    { min: 10,  max: 90  },
    temperature_reading: { min: 15,  max: 45  }
  };

  const range = ranges[eventType];
  const value = range.min + Math.random() * (range.max - range.min);

  return {
    sensor_id:  sensor,
    event_type: eventType,
    value:      parseFloat(value.toFixed(4)),
    timestamp:  Date.now() / 1000,
    location:   sensor.split('-')[1],
    unit:       eventType.includes('moisture') ? '%' :
                eventType.includes('temp')     ? 'celsius' : 'mg/kg'
  };
}

async function sendEvent(apiUrl, event) {
  return new Promise((resolve, reject) => {
    const data   = JSON.stringify(event);
    const url    = new URL(apiUrl);

    const options = {
      hostname: url.hostname,
      path:     url.pathname,
      method:   'POST',
      headers:  {
        'Content-Type':   'application/json',
        'Content-Length': Buffer.byteLength(data)
      }
    };

    const req = https.request(options, res => {
      resolve(res.statusCode);
    });

    req.on('error', reject);
    req.write(data);
    req.end();
  });
}

async function main() {
  const API_URL = process.env.API_URL;

  if (!API_URL) {
    console.error('ERROR: Set API_URL environment variable');
    process.exit(1);
  }

  const RATE = parseInt(process.env.RATE_PER_SEC || '5');
  const interval = 1000 / RATE;

  console.log(`Generating ${RATE} events/second to ${API_URL}`);

  let sent  = 0;
  let errors = 0;

  setInterval(async () => {
    const event = generateEvent();
    try {
      const status = await sendEvent(API_URL, event);
      sent++;
      if (sent % 50 === 0) {
        console.log(`Sent: ${sent} | Errors: ${errors} | Latest: ${event.sensor_id} ${event.event_type} = ${event.value}`);
      }
    } catch (err) {
      errors++;
    }
  }, interval);
}

main();