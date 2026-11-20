const query = new URLSearchParams(location.search);
document.querySelector('#message').textContent = `${query.get('name') || 'Ce nom'} : ${query.get('reason') || 'aucune destination trouvée'}`;
