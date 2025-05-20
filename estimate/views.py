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
import comtypes.client
import pythoncom

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
    estimate = get_object_or_404(Estimate, id=estimate_id, created_by=request.user)
    doc = Document('KCP_LETTERPAD.docx')
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

    # Replace in all paragraphs
    for paragraph in doc.paragraphs:
        replace_placeholders_in_element(paragraph, replacements)

    # Replace in all tables (all cells)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                replace_placeholders_in_element(cell, replacements)

    # Create temporary files
    with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as docx_file:
        docx_filename = docx_file.name
        doc.save(docx_filename)

    try:
        # Initialize COM
        pythoncom.CoInitialize()
        
        # Create Word application
        word = comtypes.client.CreateObject('Word.Application')
        word.Visible = False
        
        # Open the document
        doc = word.Documents.Open(os.path.abspath(docx_filename))
        
        # Create PDF filename
        pdf_filename = docx_filename.replace('.docx', '.pdf')
        
        # Save as PDF
        doc.SaveAs(os.path.abspath(pdf_filename), FileFormat=17)  # 17 represents PDF format
        
        # Close the document and Word
        doc.Close()
        word.Quit()
        
        # Read the generated PDF
        with open(pdf_filename, 'rb') as f:
            response = HttpResponse(f.read(), content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="KCP-ESTIMATE-{estimate.party_name}.pdf"'
        
        # Clean up temporary files
        os.remove(docx_filename)
        os.remove(pdf_filename)
        
        return response
        
    except Exception as e:
        # If PDF conversion fails, return the DOCX file
        with open(docx_filename, 'rb') as f:
            response = HttpResponse(f.read(), content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
            response['Content-Disposition'] = f'attachment; filename="KCP-ESTIMATE-{estimate.party_name}.docx"'
        os.remove(docx_filename)
        messages.warning(request, 'PDF conversion failed. Downloading DOCX file instead.')
        return response
    finally:
        # Clean up COM
        pythoncom.CoUninitialize()

@login_required
def delete_estimate(request, estimate_id):
    estimate = get_object_or_404(Estimate, id=estimate_id, created_by=request.user)
    if request.method == 'POST':
        estimate.delete()
        messages.success(request, 'Estimate deleted successfully!')
        return redirect('dashboard')
    # Optional: Render a confirmation page for GET requests
    return render(request, 'estimate/confirm_delete.html', {'estimate': estimate})
