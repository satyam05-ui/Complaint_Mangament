const express = require('express');
const mongoose = require('mongoose');
const cors = require('cors');

const app = express();
app.use(express.json());
app.use(cors()); // Allows your HTML file to connect to this server

// 1. DATABASE CONNECTION
// Replace this URL with your MongoDB Atlas URL if hosting online
mongoose.connect('mongodb://127.0.0.1:27017/grievancepro')
    .then(() => console.log('✅ MongoDB Database Connected Successfully'))
    .catch(err => console.error('❌ MongoDB Connection Error:', err));

// 2. DATABASE SCHEMAS (Models)
const userSchema = new mongoose.Schema({
    id: String,
    email: { type: String, unique: true },
    pass: String,
    name: String,
    phone: String,
    role: String
});
const User = mongoose.model('User', userSchema);

const grievanceSchema = new mongoose.Schema({
    id: { type: String, unique: true },
    fName: String,
    lName: String,
    phone: String,
    email: String,
    domain: String,
    subdomain: String,
    entity: String,
    desc: String,
    state: String,
    city: String,
    pin: String,
    priority: String,
    status: { type: String, default: 'Pending Review' },
    timestamp: String,
    date: String,
    userRef: String
});
const Grievance = mongoose.model('Grievance', grievanceSchema);

// 3. API ROUTES

// --- Users / Auth ---
app.post('/api/auth/register', async (req, res) => {
    try {
        const newUser = new User(req.body);
        await newUser.save();
        res.json({ success: true, user: newUser });
    } catch (error) {
        res.status(400).json({ success: false, message: 'Email already exists' });
    }
});

app.post('/api/auth/login', async (req, res) => {
    const { email, pass } = req.body;
    const user = await User.findOne({ email, pass });
    if (user) res.json({ success: true, user });
    else res.status(401).json({ success: false, message: 'Invalid credentials' });
});

// --- Grievances ---
app.post('/api/grievances', async (req, res) => {
    try {
        const newGrievance = new Grievance(req.body);
        await newGrievance.save();
        res.json({ success: true, grievance: newGrievance });
    } catch (error) {
        res.status(500).json({ success: false, error: error.message });
    }
});

app.get('/api/grievances', async (req, res) => {
    try {
        // Fetch all grievances, sort by newest first
        const grievances = await Grievance.find().sort({ _id: -1 });
        res.json(grievances);
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

app.patch('/api/grievances/:id/status', async (req, res) => {
    try {
        const { status } = req.body;
        const updated = await Grievance.findOneAndUpdate(
            { id: req.params.id }, 
            { status: status },
            { new: true }
        );
        res.json({ success: true, grievance: updated });
    } catch (error) {
        res.status(500).json({ success: false, error: error.message });
    }
});

// 4. START SERVER
const PORT = 5000;
app.listen(PORT, () => {
    console.log(`🚀 Enterprise Database Server running on http://localhost:${PORT}`);
});