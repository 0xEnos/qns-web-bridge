const query = new URLSearchParams(location.search);
document.querySelector('#message').textContent = `${query.get('name') || 'This name'}: ${query.get('reason') || 'no destination was found'}`;
