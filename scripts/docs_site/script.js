    // Search Script
    const SEARCH_INDEX = {{ search_index_json | safe }};
    const back_to_root = "{{ back_to_root }}";
    const searchInput = document.getElementById('search-input');
    const searchResults = document.getElementById('search-results');

    searchInput.addEventListener('input', () => {
      const query = searchInput.value.toLowerCase().trim();
      if (!query) {
        searchResults.style.display = 'none';
        return;
      }

      const matches = [];
      for (const page of SEARCH_INDEX) {
        let score = 0;
        if (page.title.toLowerCase().includes(query)) {
          score += 10;
        }
        if (page.content.toLowerCase().includes(query)) {
          score += 1;
        }
        if (score > 0) {
          matches.push({ page, score });
        }
      }

      matches.sort((a, b) => b.score - a.score);

      if (matches.length === 0) {
        searchResults.innerHTML = '<div style="padding: 0.5rem 1rem; color: var(--text-dim); font-size: 0.9rem;">No results found</div>';
      } else {
        searchResults.innerHTML = matches.map(m => {
          const relUrl = back_to_root + m.page.url;
          return `<a href="${relUrl}" style="display: block; padding: 0.5rem 1rem; color: var(--text-color); text-decoration: none; font-size: 0.9rem; border-bottom: 1px solid rgba(255,255,255,0.05); transition: background 0.2s;" onmouseover="this.style.background='rgba(255,255,255,0.05)'" onmouseout="this.style.background='transparent'"><strong style="color: var(--primary);">${m.page.title}</strong><div style="font-size: 0.8rem; color: var(--text-dim); text-overflow: ellipsis; overflow: hidden; white-space: nowrap; margin-top: 0.2rem;">${m.page.content.substring(0, 100)}...</div></a>`;
        }).join('');
      }
      searchResults.style.display = 'block';
    });

    document.addEventListener('click', (e) => {
      if (!searchInput.contains(e.target) && !searchResults.contains(e.target)) {
        searchResults.style.display = 'none';
      }
    });

    // Mobile menu toggle
    const menuToggle = document.getElementById('menuToggle');
    const sidebar = document.getElementById('sidebar');

    menuToggle.addEventListener('click', () => {
      sidebar.classList.toggle('open');
      menuToggle.textContent = sidebar.classList.contains('open') ? '✕' : '☰';
    });

    document.querySelectorAll('.sidebar-link').forEach(link => {
      link.addEventListener('click', () => {
        if (window.innerWidth <= 850) {
          sidebar.classList.remove('open');
          menuToggle.textContent = '☰';
        }
      });
    });

    // Copy to clipboard helper for code blocks
    document.querySelectorAll('pre').forEach(pre => {
      const wrapper = document.createElement('div');
      wrapper.className = 'code-wrapper';
      wrapper.style.position = 'relative';
      pre.parentNode.insertBefore(wrapper, pre);
      wrapper.appendChild(pre);

      const btn = document.createElement('button');
      btn.className = 'copy-code-btn';
      btn.innerHTML = `
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
        copy
      `;
      btn.style.position = 'absolute';
      btn.style.top = '8px';
      btn.style.right = '8px';
      btn.style.background = 'rgba(255, 255, 255, 0.08)';
      btn.style.border = '1px solid rgba(255, 255, 255, 0.15)';
      btn.style.borderRadius = '4px';
      btn.style.color = 'var(--text-dim)';
      btn.style.padding = '4px 8px';
      btn.style.fontSize = '11px';
      btn.style.cursor = 'pointer';
      btn.style.display = 'flex';
      btn.style.alignItems = 'center';
      btn.style.gap = '4px';
      btn.style.transition = 'all 0.2s';
      
      btn.addEventListener('mouseover', () => {
        btn.style.background = 'rgba(255, 255, 255, 0.15)';
        btn.style.color = 'var(--text-color)';
      });
      btn.addEventListener('mouseout', () => {
        btn.style.background = 'rgba(255, 255, 255, 0.08)';
        btn.style.color = 'var(--text-dim)';
      });

      btn.addEventListener('click', () => {
        const codeText = pre.innerText.trim();
        
        function copySuccess() {
          btn.innerHTML = 'copied!';
          setTimeout(() => {
            btn.innerHTML = `
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
              copy
            `;
          }, 2000);
        }

        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(codeText).then(copySuccess).catch(err => {
            console.error('Failed to copy: ', err);
            fallbackCopy();
          });
        } else {
          fallbackCopy();
        }

        function fallbackCopy() {
          const textArea = document.createElement("textarea");
          textArea.value = codeText;
          textArea.style.top = "0";
          textArea.style.left = "0";
          textArea.style.position = "fixed";
          document.body.appendChild(textArea);
          textArea.focus();
          textArea.select();
          try {
            document.execCommand('copy');
            copySuccess();
          } catch (err) {
            console.error('Fallback copy failed: ', err);
          }
          document.body.removeChild(textArea);
        }
      });

      wrapper.appendChild(btn);
    });

    // Helper functions for safe localStorage usage (prevents file:// exceptions)
    function safeGetLocalStorage(key) {
      try {
        return localStorage.getItem(key);
      } catch (e) {
        return null;
      }
    }

    function safeSetLocalStorage(key, value) {
      try {
        localStorage.setItem(key, value);
      } catch (e) {}
    }

    // 1. Theme toggle switcher
    const themeToggleBtn = document.getElementById('theme-toggle-btn');
    const savedTheme = safeGetLocalStorage('theme');
    if (savedTheme === 'light') {
      document.body.classList.add('light-theme');
    } else {
      document.body.classList.remove('light-theme');
    }
    themeToggleBtn.addEventListener('click', () => {
      document.body.classList.toggle('light-theme');
      if (document.body.classList.contains('light-theme')) {
        safeSetLocalStorage('theme', 'light');
      } else {
        safeSetLocalStorage('theme', 'dark');
      }
      if (typeof updateScrollSpy === 'function') {
        updateScrollSpy();
      }
    });

    // 2. Right sidebar collapse toggle
    const rightSidebar = document.getElementById('right-sidebar');
    const rightSidebarToggle = document.getElementById('right-sidebar-toggle');
    const savedSidebarCollapsed = safeGetLocalStorage('right-sidebar-collapsed');
    
    if (savedSidebarCollapsed === 'true') {
      if (rightSidebar) rightSidebar.classList.add('collapsed');
      document.body.classList.add('right-sidebar-collapsed');
    } else {
      if (rightSidebar) rightSidebar.classList.remove('collapsed');
      document.body.classList.remove('right-sidebar-collapsed');
    }
    
    if (rightSidebarToggle) {
      rightSidebarToggle.addEventListener('click', () => {
        if (rightSidebar) {
          rightSidebar.classList.toggle('collapsed');
          const isCollapsed = rightSidebar.classList.contains('collapsed');
          if (isCollapsed) {
            document.body.classList.add('right-sidebar-collapsed');
            safeSetLocalStorage('right-sidebar-collapsed', 'true');
          } else {
            document.body.classList.remove('right-sidebar-collapsed');
            safeSetLocalStorage('right-sidebar-collapsed', 'false');
          }
        }
      });
    }

    // Compacted menu toggle with smooth height/opacity transition
    const compactTrigger = document.getElementById('compacted-menu-trigger');
    const compactExpanded = document.getElementById('compacted-menu-expanded-container');

    if (compactTrigger && compactExpanded) {
      const badge = compactTrigger.querySelector('.compact-badge');
      const initialText = badge ? badge.textContent : 'show';
      
      compactTrigger.addEventListener('click', () => {
        const isExpanded = compactExpanded.classList.toggle('expanded');
        if (isExpanded) {
          compactExpanded.style.height = compactExpanded.scrollHeight + 'px';
          if (badge) badge.textContent = 'hide';
        } else {
          compactExpanded.style.height = '0px';
          if (badge) badge.textContent = initialText;
        }
      });
    }

    // Path Copy-to-Clipboard Helper via event delegation
    document.addEventListener('click', (e) => {
      const btn = e.target.closest('.copy-path-btn');
      if (btn) {
        const text = btn.getAttribute('data-clipboard-text');
        if (text) {
          navigator.clipboard.writeText(text).then(() => {
            const originalTitle = btn.title;
            const originalColor = btn.style.color;
            btn.style.color = 'var(--secondary)';
            btn.title = 'Copied!';
            setTimeout(() => {
              btn.style.color = originalColor;
              btn.title = originalTitle;
            }, 1000);
          }).catch(err => {
            console.error('Failed to copy path: ', err);
          });
        }
      }
    });

    // 4. Populate outline from headings
    const contentHeadings = document.querySelectorAll('.content h1, .content h2, .content h3');
    const outlineBody = document.getElementById('outline-body');
    
    if (contentHeadings.length === 0) {
      const outlineSection = document.getElementById('outline-section');
      if (outlineSection) outlineSection.style.display = 'none';
      if (rightSidebar) rightSidebar.style.display = 'none';
      const mainContainer = document.querySelector('.main-container');
      if (mainContainer) mainContainer.style.marginRight = '0';
    } else {
      const list = document.createElement('ul');
      list.className = 'outline-list';
      
      contentHeadings.forEach((heading, index) => {
        if (!heading.id) {
          heading.id = 'heading-' + index;
        }
        
        const li = document.createElement('li');
        li.className = 'outline-item';
        const a = document.createElement('a');
        a.href = '#' + heading.id;
        
        const level = parseInt(heading.tagName[1]); // 1, 2, 3
        a.className = 'outline-link outline-depth-' + level;
        // Clean text of 'copy' or '[source]' tags if they leak
        a.textContent = heading.innerText.replace(/copy\s*$/i, '').replace(/\[source\]/g, '').trim();
        
        a.addEventListener('click', (e) => {
          e.preventDefault();
          heading.scrollIntoView({ behavior: 'smooth' });
          history.pushState(null, null, '#' + heading.id);
        });
        
        li.appendChild(a);
        list.appendChild(li);
      });
      if (outlineBody) outlineBody.appendChild(list);
      
      // 5. Scrollspy Highlight Gradient Flow (Prelievanie)
      function updateScrollSpy() {
        const headings = Array.from(contentHeadings);
        if (headings.length === 0) return;
        
        const viewportHeight = window.innerHeight;
        const threshold = 120; // y-coordinate for active reading trigger
        
        let activeIdx = 0;
        for (let i = 0; i < headings.length; i++) {
          const rect = headings[i].getBoundingClientRect();
          if (rect.top <= threshold) {
            activeIdx = i;
          } else {
            break;
          }
        }
        
        const outlineLinks = document.querySelectorAll('#outline-body .outline-link');
        outlineLinks.forEach((link, idx) => {
          const heading = headings[idx];
          const rect = heading.getBoundingClientRect();
          
          link.classList.remove('active');
          link.style.opacity = '';
          link.style.color = '';
          
          if (idx === activeIdx) {
            link.classList.add('active');
            link.style.opacity = '1.0';
          } else if (idx < activeIdx) {
            // Past sections: dimmed
            link.style.opacity = '0.5';
          } else {
            // Future sections
            if (rect.top < viewportHeight) {
              // Visible future sections: shine with fading opacity gradient
              const distance = idx - activeIdx;
              const opacity = Math.max(0.3, 1.0 - distance * 0.25);
              link.style.opacity = opacity.toString();
              link.style.color = 'var(--text-color)';
            } else {
              // Non-visible future sections: fully dim
              link.style.opacity = '0.3';
            }
          }
        });
      }
      
      window.addEventListener('scroll', updateScrollSpy);
      // Run initially
      updateScrollSpy();
    }
