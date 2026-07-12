const Order = require('../models/Order');

// SEC-010: Broken tenant isolation — no user ownership check
router.get('/:id', async (req, res) => {
  const order = await Order.findById(req.params.id);
  res.json(order);
});

// SEC-010: Also broken — delete without ownership
router.delete('/:id', async (req, res) => {
  await Order.findById(req.params.id).then(o => o.remove());
  res.json({ deleted: true });
});
