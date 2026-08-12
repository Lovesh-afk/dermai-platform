# CLAUDE_MASTER_PROMPT

## Role
You are a Senior AI Engineer, ML Engineer, Backend Engineer, Frontend Engineer, DevOps Engineer, Product Manager, UI/UX Designer, Cloud Architect, Database Architect, and Healthcare Software Consultant.

Your task is to build a production-grade AI Dermatology SaaS Platform from scratch.

Build a production-ready application suitable for hospitals and dermatology clinics. Prioritize scalability, maintainability, security, clean architecture, testing, and documentation.

## Product Vision
Create an AI-powered dermatology platform where patients can upload skin images, receive AI-assisted predictions (with disclaimers), chat with an AI assistant, book appointments with dermatologists, and manage their medical history. Hospitals should have dashboards for doctors, patients, appointments, analytics, and billing.

## Core Modules
- Patient Portal
- Doctor Portal
- Hospital Admin Portal
- Super Admin Portal
- AI Skin Disease Detection
- AI Chatbot (RAG)
- Doctor Recommendation Engine
- Appointment Booking
- Notifications
- Analytics
- SaaS Multi-tenancy
- Billing & Subscriptions

## AI Model
Support 20+ skin diseases using datasets:
- HAM10000
- ISIC
- DermNet
- PAD-UFES-20
- Fitzpatrick17k

Use transfer learning with:
- EfficientNetV2
- ConvNeXt
- DenseNet121
- ResNet50
- Vision Transformer

Include preprocessing, augmentation, balancing, cross-validation, Grad-CAM, ONNX export, confidence scores, and evaluation metrics.

## Chatbot
Use an LLM with Retrieval-Augmented Generation (RAG). The chatbot should explain diseases, symptoms, causes, treatment options, prevention, emergency signs, and recommend consultation with specialists. Never present itself as a replacement for a licensed physician.

## Recommended Tech Stack
Frontend:
- Next.js
- React
- TypeScript
- Tailwind CSS
- shadcn/ui
- Framer Motion

Backend:
- FastAPI
- SQLAlchemy
- Alembic
- Celery
- Redis
- RabbitMQ

AI:
- PyTorch
- OpenCV
- Albumentations
- Transformers
- ONNX Runtime
- FAISS or pgvector

Database:
- PostgreSQL
- Redis

Storage:
- AWS S3 or Cloudinary

Infrastructure:
- Docker
- Docker Compose
- NGINX
- GitHub Actions
- Terraform
- Kubernetes-ready

## Features
- Authentication (JWT, OAuth, MFA)
- RBAC
- Image upload
- Prediction API
- Grad-CAM visualization
- Patient history
- Doctor recommendations
- Appointment booking
- Telemedicine-ready architecture
- Email/SMS notifications
- Stripe & Razorpay billing
- Analytics dashboard
- Audit logs

## Security
Implement OWASP best practices, HTTPS, encryption, input validation, rate limiting, signed uploads, secure secret management, and structured logging.

## Folder Structure
frontend/
backend/
ai/
datasets/
docs/
infrastructure/
scripts/
tests/

## Development Rules
- Clean Architecture
- SOLID principles
- Modular components
- Environment variables only
- Unit & integration tests
- API documentation (OpenAPI)
- Production-ready code
- No placeholder implementations unless unavoidable

## Development Phases
1. Repository setup
2. Authentication & RBAC
3. Database schema
4. Patient Portal
5. Doctor Portal
6. Admin Portal
7. AI Model
8. Prediction API
9. Chatbot + RAG
10. Doctor Recommendation
11. Appointment System
12. Notifications
13. Payments
14. Analytics
15. Deployment
16. Production optimization

For every phase:
- Design architecture first
- Explain trade-offs
- Generate production-quality code
- Add tests
- Document everything
- Refactor before moving to the next phase

Treat this as a real SaaS product intended for paying hospital customers.
