document.addEventListener('DOMContentLoaded', function(){
  // Preview thumbnails
  document.querySelectorAll('.preview-thumb, .preview-thumb-row').forEach(el=>{
    el.addEventListener('click', function(e){
      const id = this.dataset.id;
      if(!id) return;
      fetch('/design/' + id).then(r=>r.text()).then(html=>{
        // The preview route returns a full small template; but we'll use API style:
        // Instead we'll fetch design details via simple endpoint (or reuse data attributes)
        // Simpler approach: use dataset to read src and alt
        const img = this.tagName === 'IMG' ? this : this.querySelector('img');
        const src = img ? img.getAttribute('src') : null;
        const title = img ? img.getAttribute('alt') : 'Preview';
        const modal = new bootstrap.Modal(document.getElementById('previewModal'));
        document.getElementById('previewTitle').textContent = title;
        const previewImage = document.getElementById('previewImage');
        previewImage.src = src;
        modal.show();
      });
    });
  });

  // disable right click context menu inside preview modal and on images to make casual screenshotting less convenient
  document.addEventListener('contextmenu', function(e){
    if(e.target.closest('#previewModal') || e.target.tagName === 'IMG'){
      e.preventDefault();
    }
  });

  // Toggle featured (AJAX)
  document.querySelectorAll('.toggle-featured').forEach(btn=>{
    btn.addEventListener('click', function(){
      const id = this.dataset.id;
      fetch('/admin/designs/toggle_featured/' + id, {method:'POST'}).then(r=>r.json()).then(json=>{
        if(json.ok){
          this.textContent = json.featured ? 'Yes' : 'No';
        } else alert('Unable to toggle');
      });
    });
  });
});
