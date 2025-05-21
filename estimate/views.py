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
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
import docx2txt
from docx2pdf import convert

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
    """Replace placeholders in a paragraph or cell while preserving formatting."""
    if not hasattr(element, 'text') or not element.text:
        return

    # First, check if any replacements are needed
    needs_replacement = False
    for key in replacements:
        if key in element.text:
            needs_replacement = True
            break
    
    if not needs_replacement:
        return

    # Store the original text and formatting
    original_text = element.text
    original_runs = []
    for run in element.runs:
        original_runs.append({
            'text': run.text,
            'bold': run.bold,
            'italic': run.italic,
            'underline': run.underline,
            'font': run.font.name if run.font else None,
            'size': run.font.size if run.font else None,
            'color': run.font.color.rgb if run.font and run.font.color else None
        })

    # Clear all runs
    for run in element.runs:
        run.text = ''

    # Apply replacements to the text
    new_text = original_text
    for key, value in replacements.items():
        new_text = new_text.replace(key, str(value))

    # Add the new text with original formatting
    if original_runs:
        run = element.add_run(new_text)
        run.bold = original_runs[0]['bold']
        run.italic = original_runs[0]['italic']
        run.underline = original_runs[0]['underline']
        if original_runs[0]['font']:
            run.font.name = original_runs[0]['font']
        if original_runs[0]['size']:
            run.font.size = original_runs[0]['size']
        if original_runs[0]['color']:
            run.font.color.rgb = original_runs[0]['color']
    else:
        element.add_run(new_text)

@login_required
def generate_pdf(request, estimate_id):
    try:
        estimate = get_object_or_404(Estimate, id=estimate_id, created_by=request.user)
        template_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'KCP_LETTERPAD.docx')
        
        if not os.path.exists(template_path):
            logger.error(f"Template file not found at: {template_path}")
            messages.error(request, 'Template file not found. Please contact support.')
            return redirect('dashboard')
        
        # Create a temporary copy of the template
        with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as temp_docx:
            temp_docx_path = temp_docx.name
            with open(template_path, 'rb') as src:
                temp_docx.write(src.read())
        
        logger.info(f"Created temporary copy at: {temp_docx_path}")
        
        # Work with the copy
        doc = Document(temp_docx_path)
        current_year = str(datetime.now().year)
        
        replacements = {
            '<partyname>': estimate.party_name,
            '<date>': str(estimate.date),
            '<paverblocktype>': str(estimate.paver_block_type),
            '<rate1>': str(estimate.price),
            '<rate2>': str(estimate.gst_amount),
            '<rate3>': str(estimate.transportation_charge),
            '<rate4>': str(estimate.transportation_charge),
            '<rate5>': str(estimate.loading_unloading_cost),
            '<rate>': str(estimate.total_amount),
            '<year>': current_year,
            '<NOTE>': estimate.notes or '',
        }
        
        logger.info("Starting text replacements with values:")
        for key, value in replacements.items():
            logger.info(f"{key}: {value}")

        # Replace in all paragraphs
        for paragraph in doc.paragraphs:
            replace_placeholders_in_element(paragraph, replacements)

        # Replace in all tables (all cells)
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for paragraph in cell.paragraphs:
                        replace_placeholders_in_element(paragraph, replacements)

        # Save the modified copy
        doc.save(temp_docx_path)
        logger.info("Saved modified document")
        
        # Convert the copy to PDF
        pdf_filename = f'KCP-ESTIMATE-{estimate.party_name}.pdf'
        logger.info(f"Converting to PDF: {pdf_filename}")
        convert(temp_docx_path, pdf_filename)
        
        # Send the PDF
        with open(pdf_filename, 'rb') as f:
            response = HttpResponse(f.read(), content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="{pdf_filename}"'
        
        # Clean up temporary files
        os.remove(temp_docx_path)
        os.remove(pdf_filename)
        logger.info("Cleanup complete")
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
