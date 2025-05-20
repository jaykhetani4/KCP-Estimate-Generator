from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, authenticate
from django.contrib import messages
from django.http import HttpResponse
from docx import Document
from docx.text.paragraph import Paragraph
from docx.table import _Cell
import os
from datetime import datetime
from .models import Estimate, PaverBlockType
from .forms import CustomLoginForm, EstimateForm, PaverBlockTypeForm
import tempfile
import logging
import traceback
from docx_replace import docx_replace
import subprocess

logger = logging.getLogger(__name__)

def login_view(request):
    if request.method == 'POST':
        form = CustomLoginForm(data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                return redirect('dashboard')
    else:
        form = CustomLoginForm()
    return render(request, 'estimate/login.html', {'form': form})

@login_required
def dashboard(request):
    estimates = Estimate.objects.filter(created_by=request.user).order_by('-created_at')
    return render(request, 'estimate/dashboard.html', {'estimates': estimates})

@login_required
def create_estimate(request):
    if request.method == 'POST':
        form = EstimateForm(request.POST)
        if form.is_valid():
            estimate = form.save(commit=False)
            estimate.created_by = request.user
            estimate.save()
            messages.success(request, 'Estimate created successfully!')
            return redirect('dashboard')
    else:
        form = EstimateForm()
    return render(request, 'estimate/create_estimate.html', {'form': form})

@login_required
def manage_paver_blocks(request):
    if request.method == 'POST':
        form = PaverBlockTypeForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Paver block type added successfully!')
            return redirect('manage_paver_blocks')
    else:
        form = PaverBlockTypeForm()
    
    paver_blocks = PaverBlockType.objects.all()
    return render(request, 'estimate/manage_paver_blocks.html', {
        'form': form,
        'paver_blocks': paver_blocks
    })

@login_required
def delete_paver_block(request, paver_block_id):
    paver_block = get_object_or_404(PaverBlockType, id=paver_block_id)
    if request.method == 'POST':
        paver_block.delete()
        messages.success(request, 'Paver block type deleted successfully!')
        return redirect('manage_paver_blocks')
    return render(request, 'estimate/confirm_delete_paver_block.html', {'paver_block': paver_block})

def replace_placeholders_in_element(element, replacements):
    """Replaces placeholders in a paragraph or table cell, handling split runs."""
    
    runs_to_process = []
    if isinstance(element, Paragraph):
        runs_to_process = element.runs
    elif isinstance(element, _Cell):
        for paragraph in element.paragraphs:
            runs_to_process.extend(paragraph.runs)
    else:
        # Not a paragraph or cell we can process runs from
        return

    # Combine text from all runs to find full placeholder strings
    full_text = "".join([run.text for run in runs_to_process])

    for placeholder, value in replacements.items():
        if placeholder in full_text:
            # Find the start index of the placeholder in the combined text
            start_index = full_text.find(placeholder)
            # Calculate the end index
            end_index = start_index + len(placeholder)

            current_index = 0
            runs_involved = []

            # Identify the runs that contain parts of the placeholder
            for run in runs_to_process:
                run_start = current_index
                run_end = current_index + len(run.text)

                # Check for overlap between run text range and placeholder text range
                if max(start_index, run_start) < min(end_index, run_end):
                    runs_involved.append(run)

                current_index = run_end

            # Replace the placeholder text across the involved runs
            if runs_involved:
                # Replace the part of the placeholder in the first involved run
                first_run = runs_involved[0]
                # Calculate the position within the first run where the placeholder starts
                pos_in_first_run = start_index - full_text.find(first_run.text)
                first_run.text = first_run.text[:pos_in_first_run] + value + first_run.text[pos_in_first_run + (end_index - start_index):]

                # Clear the text in any subsequent involved runs
                for subsequent_run in runs_involved[1:]:
                    subsequent_run.text = ""

@login_required
def generate_pdf(request, estimate_id):
    try:
        estimate = get_object_or_404(Estimate, id=estimate_id, created_by=request.user)
        template_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'KCP_LETTERPAD.docx')
        
        if not os.path.exists(template_path):
            logger.error(f"Template file not found at: {template_path}")
            messages.error(request, 'Template file not found. Please contact support.')
            return redirect('dashboard')
            
        # Create temporary files
        with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as docx_file:
            docx_filename = docx_file.name
            
            # Copy template to temp file
            with open(template_path, 'rb') as src:
                with open(docx_filename, 'wb') as dst:
                    dst.write(src.read())
            
            logger.info(f"Copied template to: {docx_filename}")
            
            # Replace placeholders
            replacements = {
                '<partyname>': estimate.party_name,
                '<date>': str(estimate.date),
                '<paverblocktype>': str(estimate.paver_block_type),
                '<rate1>': str(estimate.price),
                '<rate2>': str(estimate.gst_amount),
                '<rate3>': str(estimate.transportation_charge),
                '<rate4>': str(estimate.loading_unloading_cost),
                '<rate5>': str(estimate.loading_unloading_cost),
                '<rate>': str(estimate.total_amount),
                '<year>': str(datetime.now().year),
                '<NOTE>': estimate.notes or '',
            }
            
            # Replace placeholders in the document
            docx_replace(docx_filename, replacements)
            logger.info("Replaced placeholders in document")

        try:
            # Convert to PDF using unoconv
            pdf_filename = docx_filename.replace('.docx', '.pdf')
            logger.info("Attempting PDF conversion with unoconv")
            
            # Run unoconv command
            result = subprocess.run(
                ['unoconv', '-f', 'pdf', '-o', pdf_filename, docx_filename],
                capture_output=True,
                text=True,
                check=True
            )
            
            logger.info(f"unoconv stdout: {result.stdout}")
            if result.stderr:
                logger.warning(f"unoconv stderr: {result.stderr}")
            
            if os.path.exists(pdf_filename):
                logger.info(f"PDF file created successfully at: {pdf_filename}")
                with open(pdf_filename, 'rb') as f:
                    response = HttpResponse(f.read(), content_type='application/pdf')
                    response['Content-Disposition'] = f'attachment; filename="KCP-ESTIMATE-{estimate.party_name}.pdf"'
                os.remove(pdf_filename)
                os.remove(docx_filename)
                return response
            else:
                logger.error(f"PDF file not created at expected location: {pdf_filename}")
                raise FileNotFoundError("PDF file was not created")
                
        except Exception as e:
            logger.error(f"PDF conversion failed: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            # If PDF conversion fails, return the DOCX file
            with open(docx_filename, 'rb') as f:
                response = HttpResponse(f.read(), content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
                response['Content-Disposition'] = f'attachment; filename="KCP-ESTIMATE-{estimate.party_name}.docx"'
            os.remove(docx_filename)
            messages.warning(request, 'PDF conversion failed. Downloading DOCX file instead.')
            return response

    except Exception as e:
        logger.error(f"Error in generate_pdf: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        messages.error(request, f'Error generating document: {str(e)}')
        return redirect('dashboard')

@login_required
def delete_estimate(request, estimate_id):
    estimate = get_object_or_404(Estimate, id=estimate_id, created_by=request.user)
    if request.method == 'POST':
        estimate.delete()
        messages.success(request, 'Estimate deleted successfully!')
        return redirect('dashboard')
    # Optional: Render a confirmation page for GET requests
    return render(request, 'estimate/confirm_delete.html', {'estimate': estimate})
