#!/usr/bin/env python3
"""
Tests for the release workflow ansible repository update functionality.
"""

import os
import tempfile
import subprocess
import pytest


class TestReleaseWorkflowAnsibleUpdate:
    """Test the ansible repository update logic used in the release workflow."""

    def test_version_update_sed_command(self):
        """Test that the sed command correctly updates version in ansible playbook."""
        
        # Create test content that matches the actual ansible playbook structure
        ansible_content = """---
- name: Enable SSH service
  systemd:
    name: ssh
    enabled: yes
    state: started

- name: Install webquiz package in virtual environment
  pip:
    name: webquiz==1.0.8
    virtualenv: /home/oduvan/venv_webquiz
    state: present
  become_user: oduvan

- name: Set ownership of venv_webquiz directory
  file:
    path: /home/oduvan/venv_webquiz
    owner: oduvan
    group: oduvan
    recurse: yes
"""

        # Test the sed command that will be used in the workflow
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            f.write(ansible_content)
            temp_file = f.name

        try:
            # Run the sed command (same as in the workflow)
            new_version = "1.2.3"
            sed_cmd = f"sed -i 's/name: webquiz==[0-9]\\+\\.[0-9]\\+\\.[0-9]\\+$/name: webquiz=={new_version}/' {temp_file}"
            result = subprocess.run(sed_cmd, shell=True, capture_output=True, text=True)
            
            assert result.returncode == 0, f"sed command failed: {result.stderr}"
            
            # Read the updated content
            with open(temp_file, 'r') as f:
                updated_content = f.read()
            
            # Verify the version was updated correctly
            assert "webquiz==1.2.3" in updated_content, "Version was not updated to 1.2.3"
            assert "webquiz==1.0.8" not in updated_content, "Old version still present"
            
            # Verify only one line changed
            original_lines = ansible_content.split('\n')
            updated_lines = updated_content.split('\n')
            
            lines_changed = sum(1 for orig, upd in zip(original_lines, updated_lines) if orig != upd)
            assert lines_changed == 1, f"Expected 1 line to change, but {lines_changed} lines changed"
            
        finally:
            os.unlink(temp_file)

    def test_version_update_preserves_structure(self):
        """Test that version update preserves the YAML structure."""
        
        ansible_content = """- name: Install webquiz package in virtual environment
  pip:
    name: webquiz==2.1.0
    virtualenv: /home/oduvan/venv_webquiz
    state: present
  become_user: oduvan"""

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            f.write(ansible_content)
            temp_file = f.name

        try:
            # Update to new version
            new_version = "3.0.0"
            sed_cmd = f"sed -i 's/name: webquiz==[0-9]\\+\\.[0-9]\\+\\.[0-9]\\+$/name: webquiz=={new_version}/' {temp_file}"
            result = subprocess.run(sed_cmd, shell=True, capture_output=True, text=True)
            
            assert result.returncode == 0
            
            with open(temp_file, 'r') as f:
                updated_content = f.read()
            
            # Verify the structure is preserved
            expected_lines = [
                "- name: Install webquiz package in virtual environment",
                "  pip:",
                "    name: webquiz==3.0.0",
                "    virtualenv: /home/oduvan/venv_webquiz",
                "    state: present",
                "  become_user: oduvan"
            ]
            
            actual_lines = updated_content.strip().split('\n')
            assert actual_lines == expected_lines, f"Structure not preserved. Got: {actual_lines}"
            
        finally:
            os.unlink(temp_file)

    def test_version_update_only_affects_correct_line(self):
        """Test that the sed command only affects the webquiz package line."""
        
        # Content with multiple package installations
        ansible_content = """- name: Install other package
  pip:
    name: some-package==1.0.0
    state: present

- name: Install webquiz package in virtual environment
  pip:
    name: webquiz==1.5.2
    virtualenv: /home/oduvan/venv_webquiz
    state: present
  become_user: oduvan

- name: Install another package
  pip:
    name: another-package==2.0.0
    state: present"""

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            f.write(ansible_content)
            temp_file = f.name

        try:
            # Update webquiz version
            new_version = "1.6.0"
            sed_cmd = f"sed -i 's/name: webquiz==[0-9]\\+\\.[0-9]\\+\\.[0-9]\\+$/name: webquiz=={new_version}/' {temp_file}"
            result = subprocess.run(sed_cmd, shell=True, capture_output=True, text=True)
            
            assert result.returncode == 0
            
            with open(temp_file, 'r') as f:
                updated_content = f.read()
            
            # Verify only webquiz version changed
            assert "webquiz==1.6.0" in updated_content, "webquiz version not updated"
            assert "webquiz==1.5.2" not in updated_content, "old webquiz version still present"
            assert "some-package==1.0.0" in updated_content, "other package version changed"
            assert "another-package==2.0.0" in updated_content, "another package version changed"
            
        finally:
            os.unlink(temp_file)

    def test_version_update_handles_no_match(self):
        """Test that the sed command handles files with no matching version line."""
        
        # Content without webquiz package
        ansible_content = """- name: Install other packages
  pip:
    name: some-package==1.0.0
    state: present"""

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            f.write(ansible_content)
            temp_file = f.name

        try:
            # Try to update webquiz version (should not change anything)
            new_version = "1.0.0"
            sed_cmd = f"sed -i 's/name: webquiz==[0-9]\\+\\.[0-9]\\+\\.[0-9]\\+$/name: webquiz=={new_version}/' {temp_file}"
            result = subprocess.run(sed_cmd, shell=True, capture_output=True, text=True)
            
            assert result.returncode == 0, "sed should succeed even with no matches"
            
            with open(temp_file, 'r') as f:
                updated_content = f.read()
            
            # Content should remain unchanged
            assert updated_content == ansible_content, "Content should not change when no match found"
            
        finally:
            os.unlink(temp_file)